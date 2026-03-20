import typer
import json
from typing import Optional
from pathlib import Path
from app.ai.generator import generar_test_cypress # <-- Llama al cerebro
from app.parsers.environment import extraer_variables_entorno

def generate_command(
    clean_json: Path = typer.Option(..., "--json", "-j", help="Ruta al JSON limpio"),
    dest: Path = typer.Option(..., "--dest", "-d", help="Ruta del proyecto Cypress existente"),
    env_file: Optional[Path] = typer.Option(None, "--env", "-e", help="JSON de entorno (Opcional)")
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
        
    e2e_folder = dest / "cypress" / "e2e"
    features_folder = e2e_folder / "features"
    steps_folder = e2e_folder / "step_definitions"
    
    if not features_folder.exists() or not steps_folder.exists():
        typer.secho(f"❌ La estructura de carpetas no es válida. Ejecuta 'scaffold' de nuevo.", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    for endpoint in endpoints_limpios:
        nombre_seguro = endpoint['nombre_peticion'].replace(" ", "_").replace("/", "_").lower()
        archivo_feature = features_folder / f"{nombre_seguro}.feature"
        archivo_steps = steps_folder / f"{nombre_seguro}.ts"
        
        typer.echo(f"   Generando prueba BDD para: {endpoint['nombre_peticion']}...")
        
        try:
            codigo_generado = generar_test_cypress(endpoint)
            with open(archivo_feature, 'w', encoding='utf-8') as f:
                f.write(codigo_generado["feature"])
            with open(archivo_steps, 'w', encoding='utf-8') as f:
                f.write(codigo_generado["steps"])
            typer.secho(f"   ✅ Feature y Steps creados para: {nombre_seguro}", fg=typer.colors.GREEN)
        except Exception as e:
            typer.secho(f"   ❌ Error con la IA en {endpoint['nombre_peticion']}: {e}", fg=typer.colors.RED)

    typer.secho("🎉 ¡Generación de pruebas completada!", fg=typer.colors.GREEN, bold=True)