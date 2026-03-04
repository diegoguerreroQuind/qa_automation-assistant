from typing import List, Dict, Any

def extraer_peticiones(items: List[Dict[str, Any]], prefix: str = "") -> List[Dict[str, Any]]:
    """
    Recorre recursivamente los items de Postman y extrae solo la información
    relevante de las peticiones HTTP reales (ignorando carpetas vacías o metadatos).
    """
    peticiones_limpias = []

    for item in items:
        # Si el item tiene un "item" dentro, es una carpeta.
        if "item" in item:
            # Construimos un prefijo con el nombre de la carpeta para organizar mejor luego.
            nuevo_prefix = f"{prefix}{item.get('name', 'Carpeta')}/"
            # Llamada recursiva para procesar los items dentro de esta carpeta.
            peticiones_limpias.extend(extraer_peticiones(item["item"], nuevo_prefix))
        
        # Si el item tiene "request", entonces es una petición real.
        elif "request" in item:
            request_data = item["request"]
            
            # Limpiar la URL. Postman a veces la guarda como objeto y otras como string.
            url_cruda = ""
            if isinstance(request_data.get("url"), dict):
                url_cruda = request_data["url"].get("raw", "")
            elif isinstance(request_data.get("url"), str):
                url_cruda = request_data["url"]

            # Extraer headers (solo los nombres y valores)
            headers_limpios = {}
            if "header" in request_data:
                for header in request_data["header"]:
                    if not header.get("disabled", False): # Ignorar headers apagados
                        headers_limpios[header.get("key")] = header.get("value")
            
            # Extraer el body si existe
            body_crudo = None
            if "body" in request_data and request_data["body"].get("mode") == "raw":
                body_crudo = request_data["body"].get("raw")

            # Construir el objeto limpio final
            endpoint_limpio = {
                "nombre_peticion": item.get("name", "Petición Sin Nombre"),
                "ruta_carpeta": prefix.rstrip('/'),
                "metodo": request_data.get("method", "GET"),
                "url": url_cruda,
                "headers": headers_limpios,
                "body": body_crudo
            }
            peticiones_limpias.append(endpoint_limpio)

    return peticiones_limpias