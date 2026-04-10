# app/cli.py
import typer

# Importamos los intermediarios desde nuestra nueva carpeta commands
from app.commands.postman import extract_command
from app.commands.cypress import scaffold_command
from app.commands.generate import generate_command
from app.commands.jira import fetch_jira_command

# Inicializamos la app Typer
app = typer.Typer(help="CLI para generar proyectos desde Postman y Jira.", no_args_is_help=True)

# Registramos los comandos en la app
app.command(name="extract")(extract_command)
app.command(name="scaffold")(scaffold_command)
app.command(name="generate")(generate_command)
app.command(name="fetch-jira")(fetch_jira_command)