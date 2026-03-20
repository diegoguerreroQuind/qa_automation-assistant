import typer
from pathlib import Path
from app.generators.cypress import crear_estructura_cypress

def scaffold_command(
    dest: Path = typer.Option(..., "--dest", "-d", help="Ruta donde se creará el proyecto Cypress")
):
    typer.echo(f"🏗️ Construyendo proyecto Cypress en: {dest}")
    try:
        crear_estructura_cypress(dest)
        typer.secho("✅ Proyecto creado exitosamente.", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"❌ Error al crear el proyecto: {e}", fg=typer.colors.RED)