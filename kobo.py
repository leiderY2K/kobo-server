from flask import Flask, request, jsonify, send_file
import io
from pymongo import MongoClient
import gridfs
import requests
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)

# Configuración de MongoDB
MONGO_URI = os.environ.get("MONGO_URI")

# Intentar conectar a MongoDB y verificar la conexión
try:
    client = MongoClient(MONGO_URI)
    # Verificar conexión inmediatamente
    client.admin.command('ping')
    print("Conexión exitosa a MongoDB")
except Exception as e:
    print(f"Error de conexión a MongoDB: {e}")
    
#SE define la base de datos y GridFS
db = client[os.environ.get("MONGO_DB_NAME", "kobobd")]
fs = gridfs.GridFS(db)

# Endpoint para recibir los datos de las encuestas de KoboToolbox
@app.route('/recibir-datos-kobo', methods=['POST'])
def recibir_datos():
    # Verifica si los datos vienen en formato JSON
    if not request.is_json:
        return jsonify({"error": "Los datos no están en formato JSON"}), 400
    
    datos_completos = request.get_json()
    print(datos_completos)  # Debugging
   
    # Filtrar campos necesarios
    datos_filtrados = {
        'Nombre': datos_completos.get('Nombre', ''),
        'Apellido': datos_completos.get('Apellido', ''),
        'Edad': datos_completos.get('Edad', ''),
        'Es_victima_del_conflicto_armado': datos_completos.get('_Es_victima_del_conflicto_armado', ''),
        'submitted_by': datos_completos.get('_submitted_by', ''),
        'Documento_de_identidad': datos_completos.get('Documento_de_identidad', '')
    }
   
    # 🔸 Guardar datos en MongoDB
    persona = db.Persona.insert_one(datos_filtrados)
    encuesta_id = persona.inserted_id
   
    # 🔸 Descargar y almacenar imagen
    if "_attachments" in datos_completos and len(datos_completos["_attachments"]) > 0:
        attachment = datos_completos["_attachments"][0]
        image_url = attachment["download_url"]
        filename = attachment["filename"]
        try:
            response = requests.get(image_url)
            response.raise_for_status()  # Verificar si la descarga fue exitosa
            # Guardar imagen en GridFS
            file_id = fs.put(response.content, filename=filename, contentType=attachment["mimetype"])
            # Actualizar la encuesta con la referencia de la imagen
            db.Persona.update_one({"_id": encuesta_id}, {"$set": {"imagen_id": file_id}})
            return jsonify({
                "message": "Datos filtrados y imagen almacenados correctamente",
                "encuesta_id": str(encuesta_id),
                "imagen_id": str(file_id)
            }), 200
        except requests.exceptions.RequestException as e:
            return jsonify({"error": "Error al descargar la imagen", "detalle": str(e)}), 500
    return jsonify({"message": "Datos filtrados almacenados sin imagen", "encuesta_id": str(encuesta_id)}), 200

@app.route('/ver-imagen/<imagen_id>', methods=['GET'])
def ver_imagen(imagen_id):
    try:
        # Obtener la imagen desde GridFS
        file = fs.get(imagen_id)
        return send_file(io.BytesIO(file.read()), mimetype=file.content_type)
    except gridfs.errors.NoFile:
        return jsonify({"error": "Imagen no encontrada"}), 404

# Ruta de prueba para ver que el servidor esté corriendo
@app.route('/')
def index():
    return 'Servidor Flask funcionando correctamente', 200

if __name__ == '__main__':
    # Inicia el servidor Flask
    app.run(debug=True, host='0.0.0.0', port=5000)