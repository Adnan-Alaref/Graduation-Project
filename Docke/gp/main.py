# contecst manager , delete
# uvicorn -> python main.app
# internet to postman
from ast import arg
from sqlite3.dbapi2 import connect
from typing import Optional
from fastapi import FastAPI, HTTPException, status, Response
from pydantic import BaseModel
import subprocess
import shutil
import os
import sqlite3

from pydantic.types import OptionalInt

app = FastAPI()

conn = sqlite3.connect('deployment.db', check_same_thread=False)
c = conn.cursor()
# c.execute("""CREATE TABLE deployment(
#     id INTEGER PRIMARY KEY,
#     label_name TEXT NOT NULL UNIQUE,
#     image_name TEXT,
#     container_port INTEGER,
#     port INTEGER,
#     node_port INTEGER)""")


class Deployment(BaseModel):
    label_name: str
    image_name: str
    container_port: str
    port: Optional[str]
    node_port: Optional[str]


def add_deployment_db(deployment, port, node_port):
    with conn:
        try:
            c.execute("INSERT INTO deployment (label_name,image_name,container_port,port,node_port) values (?,?,?,?,?)", (
                deployment['label_name'],
                deployment['image_name'],
                deployment['container_port'],
                port,
                node_port))
            return True
        except sqlite3.Error as err:
            return False


@app.get("/docker")
def get_deployments():
    with conn:
        c.execute("SELECT * from deployment")
        deployments = c.fetchall()
        deployments_list = []
        print((deployments))
        for deployment in deployments:
            deployments_list.append(deployment[1])
    return deployments_list


@app.get("/docker/{label_name}")
def get_single_deployment(label_name: str):
    with conn:
        c.execute(
            "SELECT node_port FROM deployment WHERE label_name=?", (label_name,))
        print(c.rowcount)
        deployment = c.fetchone()[0]
        # print("192.168.49.2:"+str(deployment))

    return "192.168.59.101:"+str(deployment)


@app.delete("/docker")
def delete_deployment(label_name: str):
    with conn:
        c.execute("DELETE FROM deployment WHERE label_name = ?", (label_name,))
        print(c.rowcount)
        if c.rowcount > 0:
            args = f"kubectl delete -f ./deployments/{label_name}-deployment.yaml"
            print(args)
            subprocess.call(args, stdout=subprocess.PIPE, shell=True)
            os.remove(f"./deployments/{label_name}-deployment.yaml")
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"deployment with name: {label_name} does not exist")


@app.post("/docker", status_code=status.HTTP_201_CREATED)
def create_deployment(deployment: Deployment):
    deployment_dict = deployment.dict()

    image_args = deployment_dict['image_name'].split('/')

    image = image_args[0]+"/"+image_args[1]
    find = ["%label_name%", "%deployment_name%", "%container_name%", "%image_name%",
            "%container_port%", "%service_name%", "%port%", "%target_port%", "%node_port%"]

    replace = []
    replace.append(deployment_dict["label_name"])
    replace.append(replace[0]+"-deployment")
    replace.append(deployment_dict['label_name'])
    replace.append(image)  # image
    replace.append(deployment_dict['container_port'])
    replace.append(replace[0]+"-service")

    with conn:
        c.execute("SELECT COUNT(*) from deployment")
        table_size = c.fetchone()[0]
        if table_size == 0:
            port = 8086
            node_port = 30000
        else:
            port = 8086+table_size
            node_port = 30000+table_size
        if not add_deployment_db(deployment_dict, str(port), (node_port)):
            return "can't create two deployments with the same name !!!"
    replace.append(str(port))
    replace.append(deployment_dict['container_port'])
    replace.append(str(node_port))
    deployment_file = replace[1]+".yaml"
    shutil.copyfile('./template.yaml', './deployments/scan.yaml')
    scan = open("deployments/scan.yaml", 'r+')
    deploy = open("deployments/"+deployment_file, 'w+')
    for i, _ in enumerate(find):
        print(i)
        args = f'bash -c "sed s#{find[i]}#{replace[i]}#g ./deployments/scan.yaml"'
        # print(args)
        deploy.seek(0)
        deploy.truncate(0)

        #subprocess.call("cat deployments\scan.yaml", shell=True)
        subprocess.call(args, stdout=deploy, shell=True)
        scan.close()
        os.remove("./deployments/scan.yaml")
        shutil.copyfile("deployments/"+deployment_file,
                        './deployments/scan.yaml')

    # subprocess.call("rm -f ./deployments/scan.yaml")

    os.remove("./deployments/scan.yaml")
    subprocess.call("kubectl apply -f "+"deployments/" +
                    deployment_file, shell=True)
    deployment_url = "192.168.59.101"
    # deployment_url = subprocess.call("minikube ip", shell=True)
    # print(deployment_url)
    # deployment_url = str(deployment_url.decode())
    deployment_url += f":{node_port}"
    return deployment_url
