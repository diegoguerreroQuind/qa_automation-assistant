import typer
import json
from pathlib import Path
from app.ai.generator import estructurar_descripcion_jira
from app.parsers.jira_extractor import extraer_historia_jira

def fetch_jira_command(
    api_json_path: Path = typer.Option("api.json", "--api", "-a", help="Ruta al archivo JSON de la API limpio")
):
    """
    Se conecta a Jira, lee la historia, cruza la info con api.json 
    y estructura los criterios en inputContex.json.
    """
    server = "https://quind-team-mcu7xlcy.atlassian.net"  
    email = "daniel.mejia@quind.io"              
    token = ""                      
    issue = "EF-11"                       

    if not api_json_path.exists():
        typer.secho(f"❌ No se encontró el archivo de API en: {api_json_path}", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    try:
        with open(api_json_path, 'r', encoding='utf-8') as f:
            api_data = json.load(f)
            api_context = json.dumps(api_data)
    except Exception as e:
        typer.secho(f"❌ Error leyendo {api_json_path}: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    typer.echo(f"🔍 Buscando el ticket {issue}...")
    
    try:
        datos_crudos = extraer_historia_jira(server, email, token, issue)
        typer.secho(f"✅ ¡Ticket {datos_crudos['key']} encontrado!", fg=typer.colors.GREEN)
        
        typer.echo(f"🧠 Cruzando Criterios de Jira con Endpoints de {api_json_path.name}...")
        estructura_ia = estructurar_descripcion_jira(datos_crudos['descripcion'], api_context)
        
        json_final = {
            "key": datos_crudos["key"],
            "resumen": datos_crudos["resumen"],
            "contexto_negocio": estructura_ia.get("contexto_negocio", ""),
            "endpoints": estructura_ia.get("endpoints", [])
        }
        
        archivo_salida = "inputContex.json"
        with open(archivo_salida, "w", encoding="utf-8") as f:
            json.dump(json_final, f, indent=4, ensure_ascii=False)
            
        typer.secho(f"💾 ¡Estructura mapeada guardada en: {archivo_salida}!", fg=typer.colors.CYAN, bold=True)
        
    except Exception as e:
        typer.secho(f"❌ Error: {e}", fg=typer.colors.RED)