from datetime import UTC, datetime
from typing import Dict, List

import networkx as nx
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Inspector


def generate_database_report(connection_string: str) -> str:
    """
    Generates a comprehensive Markdown database documentation report with ER diagram.
    
    Args:
        connection_string: SQLAlchemy-compatible database connection string
        
    Returns:
        Markdown-formatted report as a string
    """
    # Setup database connection and inspection
    engine = create_engine(connection_string)
    inspector = inspect(engine)
    
    # Collect database metadata
    db_metadata = {
        'name': engine.url.database,
        'dialect': engine.dialect.name,
        'tables': inspector.get_table_names()
    }
    
    # Initialize data structures
    graph = nx.DiGraph()
    table_metadata: Dict[str, dict] = {}
    fk_relationships: List[dict] = []
    sampled_ids: Dict[str, list] = {}
    sample_data: Dict[str, list] = {}

    # Collect schema metadata and relationships
    for table in db_metadata['tables']:
        columns = inspector.get_columns(table)
        pk = inspector.get_pk_constraint(table).get('constrained_columns', [])
        indexes = inspector.get_indexes(table)
        fks = inspector.get_foreign_keys(table)
        
        # Process foreign keys
        for fk in fks:
            process_foreign_key(table, fk, inspector, graph, fk_relationships)
        
        table_metadata[table] = {
            'columns': columns,
            'primary_keys': pk,
            'indexes': indexes,
            'foreign_keys': fks
        }

    # Process tables in dependency order
    sorted_tables = get_sorted_tables(graph, db_metadata['tables'])
    
    # Collect sample data with parent-child relationships
    collect_sample_data(engine, sorted_tables, table_metadata, sample_data, sampled_ids)
    
    # Generate Markdown report
    return generate_markdown_report(db_metadata, sorted_tables, table_metadata, 
                                  fk_relationships, sample_data)


def process_foreign_key(
    table: str,
    fk: dict,
    inspector: Inspector,
    graph: nx.DiGraph,
    fk_relationships: List[dict]
) -> None:
    """Process and record foreign key relationships with cardinality information."""
    src_col = fk['constrained_columns'][0]
    tgt_table = fk['referred_table']
    tgt_col = fk['referred_columns'][0]
    
    # Check uniqueness and nullability in source column
    src_columns = inspector.get_columns(table)
    src_col_meta = next(c for c in src_columns if c['name'] == src_col)
    is_unique = src_col_meta.get('unique', False) or src_col in inspector.get_pk_constraint(table).get('constrained_columns', [])
    is_nullable = src_col_meta['nullable']

    fk_relationships.append({
        'source_table': table,
        'source_column': src_col,
        'target_table': tgt_table,
        'target_column': tgt_col,
        'constraint_name': fk['name'],
        'is_unique': is_unique,
        'is_nullable': is_nullable
    })
    graph.add_edge(table, tgt_table)


def get_sorted_tables(graph: nx.DiGraph, tables: List[str]) -> List[str]:
    """Return tables sorted topologically with fallback to original order."""
    try:
        return list(nx.topological_sort(graph))
    except nx.NetworkXUnfeasible:
        return tables


def collect_sample_data(
    engine,
    tables: List[str],
    table_metadata: Dict[str, dict],
    sample_data: Dict[str, list],
    sampled_ids: Dict[str, list]
) -> None:
    """Collect sample data while maintaining referential integrity."""
    for table in tables:
        with engine.connect() as conn:
            # Get parent samples
            result = conn.execute(text(f"SELECT * FROM {table} LIMIT 5"))
            samples = [dict(row._mapping) for row in result]
            sample_data[table] = samples
            
            # Store IDs for child sampling
            if samples and table_metadata[table]['primary_keys']:
                pk_col = table_metadata[table]['primary_keys'][0]
                sampled_ids[table] = [row[pk_col] for row in samples]


def generate_markdown_report(
    db_metadata: dict,
    tables: List[str],
    table_metadata: Dict[str, dict],
    fk_relationships: List[dict],
    sample_data: Dict[str, list]
) -> str:
    """Generate the complete Markdown report."""
    md = []
    
    # Database Summary
    md.append("# Database Documentation Report\n")
    md.append(f"**Database Type**: {db_metadata['dialect'].capitalize()}\n")
    md.append(f"**Database Name**: {db_metadata['name']}\n")
    md.append(f"**Total Tables**: {len(db_metadata['tables'])}\n")
    md.append(f"**Generated At**: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n")
    
    # ERD Section
    md.append("## Entity Relationship Diagram\n")
    md.append("```mermaid\nerDiagram\n")
    generate_erd_section(md, tables, table_metadata, fk_relationships)
    md.append("```\n\n")
    
    # Schema Details
    md.append("## Schema Details\n")
    for table in tables:
        meta = table_metadata[table]
        md.append(f"### {table}\n")
        generate_columns_section(md, meta)
        generate_indexes_section(md, meta)
    
    # Relationships
    generate_relationships_section(md, fk_relationships)
    
    # Cardinality Report
    generate_cardinality_section(md, fk_relationships)
    
    # Data Samples
    md.append("## Data Samples\n")
    for table in tables:
        samples = sample_data[table]
        md.append(f"### {table}\n")
        generate_sample_table(md, samples)
    
    return '\n'.join(md)


def generate_erd_section(md: List[str], tables: List[str], table_metadata: Dict[str, dict], fk_relationships: List[dict]) -> None:
    """Generate Mermaid ER diagram section."""
    # Define tables with their columns
    for table in tables:
        table_upper = table.upper()
        md.append(f"    {table_upper} {{\n")
        for col in table_metadata[table]['columns']:
            col_type = str(col['type']).split('(')[0].upper()  # Simplify type names
            annotations = []
            if col['name'] in table_metadata[table]['primary_keys']:
                annotations.append("PK")
            # Check if column is a foreign key
            for fk in fk_relationships:
                if fk['source_table'] == table and fk['source_column'] == col['name']:
                    annotations.append("FK")
                    break
            annotation_str = " ".join(annotations)
            md.append(f"        {col_type} {col['name']} {annotation_str}\n")
        md.append("    }\n")
    
    # Define relationships with cardinality
    for fk in fk_relationships:
        target_table = fk['target_table'].upper()
        source_table = fk['source_table'].upper()
        source_cardinality = get_source_cardinality(fk['is_unique'], fk['is_nullable'])
        md.append(f"    {target_table} ||--{source_cardinality} {source_table} : \"{fk['constraint_name']}\"\n")


def get_source_cardinality(is_unique: bool, is_nullable: bool) -> str:
    """Determine Mermaid cardinality symbol for source side of relationship."""
    if is_unique:
        return "|o" if is_nullable else "||"
    else:
        return "o{" if is_nullable else "|{"


def generate_relationships_section(md: List[str], fk_relationships: List[dict]) -> None:
    """Generate foreign key relationships section."""
    if fk_relationships:
        md.append("## Relationships\n")
        for fk in fk_relationships:
            src = f"{fk['source_table']}.{fk['source_column']}"
            tgt = f"{fk['target_table']}.{fk['target_column']}"
            md.append(f"- `{src}` → `{tgt}` (Constraint: `{fk['constraint_name']}`)\n")
        md.append("\n")


def generate_cardinality_section(md: List[str], fk_relationships: List[dict]) -> None:
    """Generate cardinality report section."""
    cardinalities = {}
    for fk in fk_relationships:
        key = (fk['target_table'], fk['source_table'])
        if key in cardinalities:
            continue
            
        if fk['is_unique']:
            cardinality = "(1) → (1)"
        else:
            cardinality = "(1) → (N)"
            
        cardinalities[key] = f"{fk['target_table']} {cardinality} {fk['source_table']}"
    
    if cardinalities:
        md.append("## Cardinality Report\n")
        for entry in cardinalities.values():
            md.append(f"- {entry}\n")
        md.append("\n")


def generate_columns_section(md: List[str], meta: dict) -> None:
    """Generate columns table section."""
    md.append("#### Columns\n")
    md.append("| Column Name | Data Type | Nullable? | Primary Key? |\n")
    md.append("|-------------|-----------|-----------|--------------|\n")
    for col in meta['columns']:
        pk = "Yes" if col['name'] in meta['primary_keys'] else "No"
        md.append(f"| `{col['name']}` | {col['type']} | {'Yes' if col['nullable'] else 'No'} | {pk} |\n")
    md.append("\n")


def generate_indexes_section(md: List[str], meta: dict) -> None:
    """Generate indexes section."""
    if meta['indexes']:
        md.append("#### Indexes\n")
        for idx in meta['indexes']:
            columns = ", ".join(idx['column_names'])
            md.append(f"- `{idx['name']}` ({idx['type'] or 'INDEX'}) → {columns}\n")
        md.append("\n")


def generate_sample_table(md: List[str], samples: list) -> None:
    """Generate sample data table section."""
    if not samples:
        md.append("No records found.\n\n")
        return
        
    headers = samples[0].keys()
    md.append("| " + " | ".join(headers) + " |\n")
    md.append("|" + "|".join(["---"] * len(headers)) + "|\n")
    
    for row in samples:
        values = []
        for val in row.values():
            if isinstance(val, str) and len(val) > 50:
                values.append(f"{val[:47]}...")
            else:
                values.append(str(val))
        md.append("| " + " | ".join(values) + " |\n")
    md.append("\n")


if __name__ == "__main__":
    from quantalogic.tools.utils.create_sample_database import create_sample_database
    
    # Create and document sample database
    create_sample_database("sample.db")
    report = generate_database_report("sqlite:///sample.db")
    print(report)