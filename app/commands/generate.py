import typer
import json
from typing import Optional
from pathlib import Path
from app.ai.generator import generar_test_cypress
from app.parsers.environment import extraer_variables_entorno

def generate_command(
    clean_json: Path = typer.Option(..., "--json", "-j", help="Ruta al JSON limpio"),
    dest: Path = typer.Option(..., "--dest", "-d", help="Ruta del proyecto Cypress existente"),
    env_file: Optional[Path] = typer.Option(None, "--env", "-e", help="JSON de entorno (Opcional)"),
    # --- NUEVO: Opción para leer el inputContex.json ---
    context_file: Path = typer.Option("inputContex.json", "--context", "-ctx", help="Ruta al JSON de contexto de Jira") 
):
    typer.secho(f"🧠 Conectando con Gemini para generar código en {dest}...", fg=typer.colors.YELLOW)
    
    if env_file and env_file.exists():
        typer.echo(f"🌍 Procesando variables de entorno desde: {env_file.name}")
        try:
            variables = extraer_variables_entorno(env_file)
            with open(dest / "cypress.env.json", "w", encoding="utf-8") as f:
                json.dump(variables, f, indent=4)
            typer.secho(f"   ✅ Archivo cypress.env.json creado.", fg=typer.colors.GREEN)
        except Exception as e:
            typer.secho(f"   ❌ Error al procesar entorno: {e}", fg=typer.colors.RED)

    try:
        with open(clean_json, 'r', encoding='utf-8') as f:
            endpoints_limpios = json.load(f)
    except Exception as e:
        typer.secho(f"❌ Error leyendo {clean_json}: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    # --- NUEVA LÓGICA: Leer Jira (inputContex.json) y crear un mapa por endpoint ---
    mapa_casos_jira = {}
    if context_file.exists():
        try:
            with open(context_file, 'r', encoding='utf-8') as f:
                contexto_jira = json.load(f)
                for ep in contexto_jira.get("endpoints", []):
                    nombre = ep.get("nombre_endpoint")
                    if nombre:
                        # Guardamos los casos usando el nombre del endpoint en minúsculas como llave
                        mapa_casos_jira[nombre.lower()] = ep.get("criterios_aceptacion", [])
            typer.secho(f"📖 Contexto de Jira cargado exitosamente desde {context_file.name}.", fg=typer.colors.CYAN)
        except Exception as e:
            typer.secho(f"⚠️ Error leyendo {context_file}: {e}", fg=typer.colors.YELLOW)
    # -------------------------------------------------------------------------------

    e2e_folder = dest / "cypress" / "e2e"
    features_folder = e2e_folder / "features"
    steps_folder = e2e_folder / "step_definitions"
    
    if not features_folder.exists() or not steps_folder.exists():
        typer.secho(f"❌ La estructura de carpetas no es válida. Ejecuta 'scaffold' de nuevo.", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    for endpoint in endpoints_limpios:
        nombre_original = endpoint['nombre_peticion']
        nombre_seguro = nombre_original.replace(" ", "_").replace("/", "_").lower()
        archivo_feature = features_folder / f"{nombre_seguro}.feature"
        archivo_steps = steps_folder / f"{nombre_seguro}.ts"
        
        # --- NUEVO: Buscar si hay casos de Jira para este endpoint específico ---
        casos_para_este_endpoint = mapa_casos_jira.get(nombre_original.lower(), [])
        
        if casos_para_este_endpoint:
            typer.echo(f"   ⚙️  Generando BDD para: {nombre_original} (Con {len(casos_para_este_endpoint)} casos de Jira)...")
        else:
            typer.echo(f"   ⚙️  Generando BDD para: {nombre_original} (Happy Path genérico)...")
        # -------------------------------------------------------------------------
        
        try:
            # --- ACTUALIZADO: Ahora le pasamos la lista de casos de Jira ---
            codigo_generado = generar_test_cypress(endpoint, casos_para_este_endpoint)
            
            with open(archivo_feature, 'w', encoding='utf-8') as f:
                f.write(codigo_generado["feature"])
            with open(archivo_steps, 'w', encoding='utf-8') as f:
                f.write(codigo_generado["steps"])
            typer.secho(f"   ✅ Feature y Steps creados para: {nombre_seguro}", fg=typer.colors.GREEN)
        except Exception as e:
            typer.secho(f"   ❌ Error con la IA en {nombre_original}: {e}", fg=typer.colors.RED)

    typer.secho("🎉 ¡Generación de pruebas completada!", fg=typer.colors.GREEN, bold=True)