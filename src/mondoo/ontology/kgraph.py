from __future__ import annotations
from pathlib    import Path
from typing     import Iterable
from rdflib     import Dataset, URIRef, BNode, Literal

import csv
import json
import random
import os
import logging

logger = logging.getLogger(__name__)

class KGraph:
    """
    A lightweight wrapper around RDFLib Dataset for working with
    multiple TriG files, SPARQL queries, and Sigma.js visualization.
    """

    def __init__(self):
        self.dataset = Dataset()
        self.files: list[Path] = []

    # ============================================================
    # 1. Loading
    # ============================================================

    def load(
        self,
        files: str | Path | Iterable[str | Path],
    ) -> "KGraph":
        """
        Load one or multiple .trig files into the RDFLib Dataset.

        Examples:
            kg.load("cc_films.trig")

            kg.load([
                "cc_films.trig",
                "cc_persons.trig",
            ])

            kg.load(Path("data"))
        """

        # Single path
        if isinstance(files, (str, Path)):
            path = Path(files)

            # Directory
            if path.is_dir():
                paths = sorted(path.glob('*.trig'))

            # Single file
            else:
                paths = [path]

        # Multiple files
        else:
            paths = [Path(p) for p in files]

        for path in paths:
            if not path.exists():
                raise FileNotFoundError(path)

            if path.suffix.lower() != '.trig':
                raise ValueError(
                    f"Expected a .trig file: {path}"
                )

            print(
                f"Loading: {path}"
            )

            self.dataset.parse(path, format='trig')
            self.files.append(path)

        print(
            f"Loaded {len(paths)} file(s). "
            f"Total triples: {len(self.dataset):,}"
        )

        return self

    # ============================================================
    # 2. SPARQL
    # ============================================================

    def sparql(
        self,
        query : str,
        *,
        csv_file     : str | Path | None = None,
        print_result : bool = True,
    ):
        """
        Execute a SPARQL query.

        For SELECT queries:
            - prints a DBpedia-like table
            - optionally writes CSV
            - returns list[dict]

        For ASK:
            - returns bool

        For CONSTRUCT/DESCRIBE:
            - returns RDFLib Graph
        """

        result = self.dataset.query(query)

        # --------------------------------------------------------
        # SELECT
        # --------------------------------------------------------

        if result.type == 'SELECT':

            variables = [
                str(variable)
                for variable in result.vars
            ]

            rows = []

            for row in result:
                values = {}

                for variable in variables:
                    value = row[variable]

                    values[variable] = (
                        self._format_rdf_value(value)
                        if value is not None
                        else ''
                    )

                rows.append(values)

            if print_result:
                self._print_table(
                    variables,
                    rows,
                )

            if csv_file is not None:
                self._write_csv(
                    csv_file,
                    variables,
                    rows,
                )

            return rows

        # --------------------------------------------------------
        # ASK
        # --------------------------------------------------------

        if result.type == 'ASK':
            value = bool(result)

            if print_result:
                print(value)

            return value

        # --------------------------------------------------------
        # CONSTRUCT / DESCRIBE
        # --------------------------------------------------------

        if result.type in ("CONSTRUCT", "DESCRIBE"):
            return result.graph

        return result

    # ============================================================
    # SPARQL helpers
    # ============================================================

    @staticmethod
    def _format_rdf_value(value) -> str:
        """
        Format RDFLib values in a human-readable way.
        """

        if isinstance(value, URIRef):
            return str(value)

        if isinstance(value, BNode):
            return f"_:{value}"

        if isinstance(value, Literal):
            return str(value)

        return str(value)

    @staticmethod
    def _print_table(
        columns : list[str],
        rows    : list[dict],
    ):
        """
        Print a DBpedia-SPARQL-style result table.
        """

        if not columns:
            print("(no variables)")
            return

        # Convert values to strings
        table = [
            [str(row.get(column, "")) for column in columns]
            for row in rows
        ]

        # Determine column widths
        widths = []

        for i, column in enumerate(columns):
            max_value_width = max(
                [len(row[i]) for row in table],
                default=0,
            )

            widths.append(
                max(len(column), max_value_width)
            )

        # Header
        header = " | ".join(
            column.ljust(widths[i])
            for i, column in enumerate(columns)
        )

        separator = "-+-".join(
            "-" * width
            for width in widths
        )

        print()
        print(header)
        print(separator)

        # Rows
        for row in table:
            print(
                " | ".join(
                    value.ljust(widths[i])
                    for i, value in enumerate(row)
                )
            )

        print()
        print(
            f"{len(rows):,} result(s)"
        )

    @staticmethod
    def _write_csv(
        filename : str | Path,
        columns  : list[str],
        rows     : list[dict],
    ):
        """
        Write SELECT results to CSV.
        """

        filename = Path(filename)

        with filename.open(
            'w',
            newline='',
            encoding='utf-8',
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=columns,
            )

            writer.writeheader()
            writer.writerows(rows)

        print(
            f"CSV written to: {filename}"
        )

    # ============================================================
    # 3. Sigma.js export
    # ============================================================

    def to_sigma(
        self,
        output_file : str | Path | None = None,
        *,
        entity_ratio       : float = 1.0,
        random_seed        : int = 42,
        include_literals   : bool = False,
        include_graph      : bool = True,
        predicates         : set[str] | None = None,
        exclude_predicates : set[str] | None = None,
    ) -> dict:
        """
        Convert the RDF dataset into Sigma.js / Graphology JSON.

        Parameters
        ----------
        entity_ratio:
            Fraction of entities to visualize.

            1.0 = 100%
            0.5 = 50%
            0.1 = 10%
            0.01 = 1%

        include_literals:
            If False, literals such as "Star Wars" and "1977"
            are kept out of the graph.

        predicates:
            If specified, only these predicates are included.

        exclude_predicates:
            Predicates to exclude.

        include_graph:
            Preserve the TriG named graph as edge metadata.
        """

        if not 0 < entity_ratio <= 1:
            raise ValueError(
                "entity_ratio must be between 0 and 1"
            )

        # --------------------------------------------------------
        # Collect entities
        # --------------------------------------------------------

        nodes: dict[str, dict] = {}

        for graph in self.dataset.graphs():

            for s, p, o in graph:

                # Subject
                if isinstance(s, (URIRef, BNode)):
                    self._add_node(
                        nodes,
                        s,
                    )

                # Object
                if isinstance(o, (URIRef, BNode)):
                    self._add_node(
                        nodes,
                        o,
                    )

                elif include_literals and isinstance(o, Literal):
                    # Optional literal nodes
                    literal_id = f'literal:{o}'

                    if literal_id not in nodes:
                        nodes[literal_id] = {
                            'id'    : literal_id,
                            'label' : str(o),
                            'type'  : 'literal',
                        }

        print(
            f"Entities found: {len(nodes):,}"
        )

        # --------------------------------------------------------
        # Sample entities
        # --------------------------------------------------------

        random.seed(random_seed)

        node_ids = list(nodes.keys())

        sample_size = max(
            1,
            int(len(node_ids) * entity_ratio),
        )

        selected_ids = set(
            random.sample(
                node_ids,
                sample_size,
            )
        )

        print(
            f"Entities selected: "
            f"{len(selected_ids):,}"
        )

        # --------------------------------------------------------
        # Build nodes
        # --------------------------------------------------------

        sigma_nodes = [
            nodes[node_id]
            for node_id in selected_ids
        ]

        # --------------------------------------------------------
        # Build edges
        # --------------------------------------------------------

        sigma_edges = []

        edge_id = 0

        for graph in self.dataset.graphs():

            graph_id = str(graph.identifier)

            for s, p, o in graph:

                # Predicate filtering
                predicate = str(p)

                if (
                    predicates is not None
                    and predicate not in predicates
                ):
                    continue

                if (
                    exclude_predicates is not None
                    and predicate in exclude_predicates
                ):
                    continue

                source = str(s)

                # ------------------------------------------------
                # Resource object
                # ------------------------------------------------

                if isinstance(o, (URIRef, BNode)):

                    target = str(o)

                    if (
                        source not in selected_ids
                        or target not in selected_ids
                    ):
                        continue

                # ------------------------------------------------
                # Literal object
                # ------------------------------------------------

                elif (
                    include_literals
                    and isinstance(o, Literal)
                ):
                    target = f"literal:{o}"

                    if source not in selected_ids:
                        continue

                else:
                    continue

                edge = {
                    "id": f"e{edge_id}",
                    "source": source,
                    "target": target,
                    "label": predicate,
                }

                if include_graph:
                    edge["graph"] = graph_id

                sigma_edges.append(edge)

                edge_id += 1

        # --------------------------------------------------------
        # Result
        # --------------------------------------------------------

        result = {
            "nodes" : sigma_nodes,
            "edges" : sigma_edges,
        }

        print(
            f"Sigma nodes: {len(sigma_nodes):,}"
        )

        print(
            f"Sigma edges: {len(sigma_edges):,}"
        )

        # --------------------------------------------------------
        # Write JSON
        # --------------------------------------------------------

        if output_file is not None:

            output_file = Path(output_file)

            with output_file.open('w', encoding='utf-8') as f:
                json.dump(
                    result,
                    f,
                    ensure_ascii = False,
                    indent       = 2,
                )

            print(
                f"Sigma JSON written to: "
                f"{output_file}"
            )

        return result

    @staticmethod
    def _add_node(
        nodes : dict[str, dict],
        value,
    ):
        """
        Add an RDF resource to the Sigma node collection.
        """

        node_id = str(value)

        if node_id in nodes:
            return

        if isinstance(value, BNode):
            label     = f"_:{value}"
            node_type = "blank-node"

        else:
            label = str(value)
            node_type = "resource"

        nodes[node_id] = {
            "id": node_id,
            "label": label,
            "type": node_type,
        }

    # ============================================================
    # Dataset statistics
    # ============================================================

    def stats(self):
        """
        Print basic dataset statistics.
        """

        graphs = list(self.dataset.graphs())

        print()
        print("========== KGraph Statistics ==========")
        print(f"Files:   {len(self.files):,}")
        print(f"Graphs:  {len(graphs):,}")
        print(f"Triples: {len(self.dataset):,}")
        print()

        for graph in graphs:
            print(
                f"{graph.identifier}: "
                f"{len(graph):,} triples"
            )


def _get_sparql_helper_(file_name):
    base_dir = './template/sparql'
    return Path(os.path.join(base_dir, file_name)).read_text()


if __name__ == '__main__':
    data_files_dir = '/Users/breeze/miscs/doi-10.17026-dans-z64-mrvb'

    class_stats   = _get_sparql_helper_('class_stats.query')
    graph_stats   = _get_sparql_helper_('graph_stats.query')
    inst_stats    = _get_sparql_helper_('instances_stats.query')
    prop_stats    = _get_sparql_helper_('property_stats.query')
    literal_stats = _get_sparql_helper_('literal_stats.query')

    query = literal_stats

    kg = KGraph()
    kg.load(data_files_dir)
    kg.sparql(query)