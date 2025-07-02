# tracker.py
import json
from collections import Counter
from flask import Flask, jsonify, request

app = Flask(__name__)
peers = []  # Lista de nodos en la red
pendingRequests = []  # Solicitudes pendientes

@app.route('/enterNetwork', methods=['POST'])
def enterNetwork():
    potencialPeer = json.loads(request.data)
    registredIP = [peer["IP"] for peer in peers]

    if potencialPeer['IP'] in registredIP:
        return jsonify({'location': 'Nodo ya perteneciente a la red bitTorrent'}), 200

    if "port" not in potencialPeer:
        return jsonify({"error": "Debe especificar el puerto de escucha del nodo."}), 400

    peers.append(potencialPeer)
    print(peers)
    return jsonify({'location': 'Se ha agregado su nodo a la red.'}), 201

@app.route('/peers', methods=['GET'])
def getPeers():
    return jsonify(peers)

@app.route('/verifyPendingDownloads', methods=['POST'])
def verifyPendingDownloads():
    peerInfo = json.loads(request.data)
    req = next((r for r in pendingRequests if r["IP"] == peerInfo["IP"]), None)
    if req is None:
        return jsonify({'message': 'No hay descargas pendientes.'}), 200
    return jsonify({"pendingRequests": pendingRequests, 'message': 'Hya descargas pendientes.'}), 200

@app.route('/updatePeers', methods=['POST'])
def updatePeers():
    newPeerInfo = json.loads(request.data)
    req = next((r for r in pendingRequests if r["File2Download"] == newPeerInfo["fileName"] and r["IP"] == newPeerInfo["IP"]), None)
    if req is None:
        return jsonify({'error': 'No se identifico la solicitud de descarga.'}), 404

    for dic in req["peersAndLeechers"]:
        if dic["IP"] == newPeerInfo["peerIP"]:
            dic["trackerSegment"] = newPeerInfo["currentSegments"] + 1
            if dic["trackerSegment"] == dic["LastFile"]:
                req["peersAndLeechers"].remove(dic)
            break

    peer = next((p for p in peers if newPeerInfo['IP'] == p["IP"]), None)
    if peer is None:
        return jsonify({'error': 'No se identifico el peer.'}), 404

    file = next((f for f in peer["Files"] if f["fileName"] == newPeerInfo["fileName"]), None)
    if file is None:
        peer["Files"].append({
            "fileName": newPeerInfo["fileName"],
            "numSegments": newPeerInfo["numSegments"],
            "currentSegments": newPeerInfo["currentSegments"]
        })
        return jsonify({'messsage': 'Se ha actualizado el estatus del peer.'}), 200

    file["currentSegments"] = newPeerInfo["currentSegments"]
    return jsonify({'messsage': 'Se ha actualizado el estatus del peer.'}), 200

@app.route('/addFile/<ip>', methods=['PUT'])
def addFile(ip):
    peer = next((p for p in peers if p['IP'] == ip), None)
    if peer is None:
        return jsonify({'error': 'No se identifico el peer.'}), 404

    updatedFiles = json.loads(request.data)
    auxDic = {file["fileName"]: file for file in peer["Files"]}
    for file in updatedFiles["addedFiles"]:
        auxDic[file["fileName"]] = file
    peer["Files"] = list(auxDic.values())

    return jsonify(peers), 200

@app.route('/allFiles', methods=['GET'])
def showFiles():
    allFiles = set()
    for peer in peers:
        for file in peer["Files"]:
            allFiles.add(file["fileName"])
    return jsonify({'Files': list(allFiles)}), 200

@app.route('/downloadFile', methods=['POST'])
def downloadFile():
    info = json.loads(request.data)
    availablePeers = []

    for peer in peers:
        for file in peer["Files"]:
            if file["fileName"] == info["fileName"] and file["currentSegments"] / file["numSegments"] >= 0.2:
                availablePeers.append({
                    "IP": peer["IP"],
                    "port": peer.get("port", 5001),
                    "currentSegments": file["currentSegments"],
                    "numSegments": file["numSegments"]
                })

    availablePeers = sorted(availablePeers, key=lambda x: x["currentSegments"])
    from collections import Counter
    count = Counter(peer["numSegments"] for peer in availablePeers)
    sortedSegments = sorted(count.keys())
    ranges = []
    start = -1

    for num in sortedSegments:
        occurrences = count[num]
        rangeSize = num - start
        base_size = rangeSize // occurrences
        extra = rangeSize % occurrences
        for i in range(occurrences):
            end = start + base_size + (1 if i < extra else 0)
            ranges.append((start + 1, end))
            start = end

    for i, peer in enumerate(availablePeers):
        peer["StartingFile"] = ranges[i][0]
        peer["LastFile"] = ranges[i][1]
        peer["trackerSegment"] = ranges[i][0]

    pendingRequests.append({
        "IP": info["IP"],
        "File2Download": info["fileName"],
        "peersAndLeechers": availablePeers
    })

    return jsonify({
        'Status': 'Se han encontrado peers y seeders para proveer los archivos.',
        'information': {
            "IP": info["IP"],
            "File2Download": info["fileName"],
            "peersAndLeechers": availablePeers
        }
    }), 200

@app.route('/pendingDownloads', methods=['GET'])
def pendingDownloads():
    return jsonify(pendingRequests)

if __name__ == '__main__':
    app.run(port=5000, host="192.168.191.120", debug=True, threaded=True)
