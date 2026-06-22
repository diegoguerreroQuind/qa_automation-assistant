"""
Capa de repositorios — aísla el acceso a SQLAlchemy del resto del backend.

Cada repositorio encapsula las queries de un agregado (Execution, Endpoint, …)
para que routers y servicios no construyan SQL inline. Esto mejora la
testabilidad (se puede mockear el repositorio) y mantiene los routers como
orquestación HTTP delgada, sin lógica de persistencia.

Patrón objetivo del Modular Monolith (ver docs/architecture-roadmap.md): a
medida que se migren los módulos, cada uno tendrá su propio repositorio aquí o
dentro de su carpeta de módulo.
"""
