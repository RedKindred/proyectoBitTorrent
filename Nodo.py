import json
from flask import Flask, jsonify, send_file, request
import threading
import requests
import os

app = Flask(__name__)

@app.route('/downloadFile', methods=['POST'])
def download_file():
    data = request.get_json()
    fileName = data.get("fileName")
    segmentNumber = data.get("segmentNumber")

    if not fileName or segmentNumber is None:
        return jsonify({"error": "Faltan parámetros"}), 400

    basePath = os.path.join(os.path.dirname(__file__), fileName + "Segment")
    filePath = os.path.join(basePath, f"fragment_{segmentNumber}.part")

    if not os.path.exists(filePath):
        return jsonify({"error": "El archivo no existe"}), 404

    return send_file(filePath, as_attachment=True)

def segmentFile(filesList):
    currentFragments = []
    for file in filesList:
        if not os.path.exists(file + "Segment"):
            os.makedirs(file + "Segment")
            with open(file, 'rb') as archivo:
                fragments = 0
                while fragmento := archivo.read(10240):
                    ruta_fragmento = os.path.join(file + "Segment", f'fragment_{fragments}.part')
                    with open(ruta_fragmento, 'wb') as f:
                        f.write(fragmento)
                    fragments += 1
        currentFragments.append({"fileName": file, "numSegments": fragments, "currentSegments": fragments})
    return currentFragments

def clientTask():
    deviceIp = input("Ingresa la IP de este nodo: ")
    devicePort = int(input("Ingresa el puerto en el que está corriendo este nodo: "))

    filesInput = input("Archivos iniciales para compartir (ej. hola.txt): ")
    filesList = [file.strip() for file in filesInput.split(',')]
    currentFragments = segmentFile(filesList)

    payload = {
        "IP": deviceIp,
        "port": devicePort,
        "Files": currentFragments
    }

    requests.post("http://192.168.191.120:5000/enterNetwork", json=payload)

    while True:
        option = input("1) Agregar archivo\n2) Descargar archivo\n3) Salir\nOpción: ")
        if option == "1":
            filesInput = input("Archivos a agregar (ej. nuevo.txt): ")
            filesList = [file.strip() for file in filesInput.split(',')]
            currentFragments = segmentFile(filesList)
            requests.put(f"http://192.168.191.120:5000/addFile/{deviceIp}", json={"addedFiles": currentFragments})
        elif option == "2":
            response = requests.get("http://192.168.191.120:5000/allFiles")
            print("Archivos disponibles:", response.json()['Files'])
            desiredFile = input("Archivo a descargar: ")
            info = {"fileName": desiredFile, "IP": deviceIp}
            response = requests.post("http://192.168.191.120:5000/downloadFile", json=info)
            if response.status_code == 200:
                peers = response.json()["information"]["peersAndLeechers"]
                for peer in peers:
                    for i in range(peer["StartingFile"], peer["LastFile"]):
                        url = f"http://{peer['IP']}:{peer['port']}/downloadFile"
                        r = requests.post(url, json={"fileName": desiredFile, "segmentNumber": i})
                        if r.status_code == 200:
                            os.makedirs(desiredFile + "Segment", exist_ok=True)
                            with open(f"{desiredFile}Segment/fragment_{i}.part", "wb") as f:
                                f.write(r.content)
                            requests.post("http://192.168.191.120:5000/updatePeers", json={
                                "fileName": desiredFile,
                                "IP": deviceIp,
                                "currentSegments": i,
                                "numSegments": peer["numSegments"],
                                "peerIP": peer["IP"]
                            })
                # Reconstruir
                with open(desiredFile, "wb") as final_file:
                    fragmentos = sorted(os.listdir(desiredFile + "Segment"), key=lambda x: int(x.split('_')[1].split('.')[0]))
                    for frag in fragmentos:
                        with open(desiredFile + "Segment/" + frag, "rb") as f:
                            final_file.write(f.read())
                print(f"Archivo reconstruido: {desiredFile}")
        elif option == "3":
            break

if __name__ == '__main__':
    port = int(input("Puerto para este nodo Flask (ej. 6001): "))
    threading.Thread(target=clientTask).start()
    app.run(host="0.0.0.0", port=port, debug=False)
