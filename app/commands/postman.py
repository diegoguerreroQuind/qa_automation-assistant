import typer
import json
from typing import Optional
from pathlib import Path
from app.parsers.postman import extraer_peticiones

def extract_command(
    collection: Path = typer.Option(..., "--collection", "-c", help="Ruta al JSON de Postman"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Archivo de salida")
):
    try:
        with open(collection, 'r', encoding='utf-8') as f:
            postman_data = json.load(f)
            
        raw_items = postman_data.get("item", [])
        endpoints_limpios = extraer_peticiones(raw_items)
        
        typer.secho(f"✅ Se encontraron {len(endpoints_limpios)} peticiones válidas.", fg=typer.colors.GREEN)

        if output:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(endpoints_limpios, f, indent=4)
            typer.secho(f"💾 Archivo limpio guardado en: {output}", fg=typer.colors.GREEN)
        else:
            typer.echo(json.dumps(endpoints_limpios, indent=2))
    except Exception as e:
        typer.secho(f"❌ Error: {e}", fg=typer.colors.RED)