# app/cli.py
import typer
import json
from typing import Optional
from pathlib import Path

# Importamos desde nuestra nueva estructura
from app.ai.generator import generar_test_cypress
from app.parsers.postman import extraer_peticiones
from app.generators.cypress import crear_estructura_cypress
from app.parsers.environment import extraer_variables_entorno  # <-- NUEVO IMPORT

app = typer.Typer(help="CLI para generar proyectos desde Postman.", no_args_is_help=True)


# -- Fase 1: Extraer datos de Postman y limpiarlos--

@app.command()
def extract(
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


# -- Fase 2: Crear proyecto Cypress--

@app.command()
def scaffold(
    dest: Path = typer.Option(..., "--dest", "-d", help="Ruta donde se creará el proyecto Cypress")
):
    typer.echo(f"🏗️ Construyendo proyecto Cypress en: {dest}")
    try:
        crear_estructura_cypress(dest)
        typer.secho("✅ Proyecto creado exitosamente.", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"❌ Error al crear el proyecto: {e}", fg=typer.colors.RED)


# -- Fase 3: Generar pruebas IA--

@app.command()
def generate(
    clean_json: Path = typer.Option(..., "--json", "-j", help="Ruta al JSON limpio (ej. api_limpia.json)"),
    dest: Path = typer.Option(..., "--dest", "-d", help="Ruta del proyecto Cypress existente (ej. ./mi-proyecto-qa)"),
    env_file: Optional[Path] = typer.Option(None, "--env", "-e", help="Ruta al JSON de entorno de Postman (Opcional)") # <-- NUEVO PARÁMETRO
):
    """
    Toma el JSON ya limpio y genera ÚNICAMENTE las pruebas IA en la carpeta indicada.
    """
    typer.secho(f"🧠 Conectando con Gemini para generar código en {dest}...", fg=typer.colors.YELLOW)
    
    # --- LÓGICA EXISTENTE: Procesar variables de entorno ---
    if env_file:
        if env_file.exists():
            typer.echo(f"🌍 Procesando variables de entorno desde: {env_file.name}")
            try:
                variables = extraer_variables_entorno(env_file)
                with open(dest / "cypress.env.json", "w", encoding="utf-8") as f:
                    json.dump(variables, f, indent=4)
                typer.secho(f"   ✅ Archivo cypress.env.json creado con {len(variables)} variables.", fg=typer.colors.GREEN)
            except Exception as e:
                typer.secho(f"   ❌ Error al procesar entorno: {e}", fg=typer.colors.RED)
        else:
            typer.secho(f"   ⚠️ El archivo de entorno {env_file} no existe. Se omitirá.", fg=typer.colors.YELLOW)
    # ---------------------------------------------------

    try:
        with open(clean_json, 'r', encoding='utf-8') as f:
            endpoints_limpios = json.load(f)
    except Exception as e:
        typer.secho(f"❌ Error leyendo {clean_json}: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    # --- NUEVA LÓGICA CUCUMBER: Rutas actualizadas ---
    e2e_folder = dest / "cypress" / "e2e"
    features_folder = e2e_folder / "features"
    steps_folder = e2e_folder / "step_definitions"
    
    # Validamos que la nueva estructura exista
    if not features_folder.exists() or not steps_folder.exists():
        typer.secho(f"❌ La estructura de carpetas no es válida para Cucumber. Ejecuta 'scaffold' de nuevo.", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    for endpoint in endpoints_limpios:
        nombre_seguro = endpoint['nombre_peticion'].replace(" ", "_").replace("/", "_").lower()
        archivo_feature = features_folder / f"{nombre_seguro}.feature"
        archivo_steps = steps_folder / f"{nombre_seguro}.ts"
        
        typer.echo(f"   Generando prueba BDD para: {endpoint['nombre_peticion']}...")
        
        try:
            # Ahora la función nos devuelve un diccionario con ambas partes
            codigo_generado = generar_test_cypress(endpoint)
            
            # Guardamos el archivo .feature
            with open(archivo_feature, 'w', encoding='utf-8') as f:
                f.write(codigo_generado["feature"])
                
            # Guardamos el archivo .ts (Step definitions)
            with open(archivo_steps, 'w', encoding='utf-8') as f:
                f.write(codigo_generado["steps"])
                
            typer.secho(f"   ✅ Feature y Steps creados para: {nombre_seguro}", fg=typer.colors.GREEN)
        except Exception as e:
            typer.secho(f"   ❌ Error con la IA en {endpoint['nombre_peticion']}: {e}", fg=typer.colors.RED)

    typer.secho("🎉 ¡Generación de pruebas completadaaaaa!", fg=typer.colors.GREEN, bold=True)