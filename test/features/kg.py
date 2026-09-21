from mondoo.ontology.kgraph import KGraph
from pathlib import Path

import os


def _get_sparql_helper_(
    file_name : str,
    *, 
    dir_name  : str | None = None
):
    base_dir = './template/sparql'

    if dir_name is None:
        return Path(os.path.join(base_dir, file_name)).read_text()
    else:
        return Path(os.path.join(dir_name, file_name)).read_text()

    
if __name__ == '__main__':
    data_files_dir = '/Users/breeze/data/doi-10.17026-dans-z64-mrvb'

    class_stats   = _get_sparql_helper_('class_stats.query')
    graph_stats   = _get_sparql_helper_('graph_stats.query')
    inst_stats    = _get_sparql_helper_('instances_stats.query')
    prop_stats    = _get_sparql_helper_('property_stats.query')
    literal_stats = _get_sparql_helper_('literal_stats.query')

    custom_query = _get_sparql_helper_('custom_sparql.query', dir_name='/Users/breeze/workspace/op')

    query = custom_query

    kg = KGraph()
    kg.load(data_files_dir)
    kg.sparql(query)