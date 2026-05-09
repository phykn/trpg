create table if not exists graph_nodes (
  game_id text not null,
  node_id text not null,
  node_type text not null,
  properties jsonb not null default '{}'::jsonb,
  primary key (game_id, node_id)
);

create table if not exists graph_edges (
  game_id text not null,
  edge_id text not null,
  edge_type text not null,
  from_node_id text not null,
  to_node_id text not null,
  properties jsonb not null default '{}'::jsonb,
  primary key (game_id, edge_id),
  foreign key (game_id, from_node_id)
    references graph_nodes(game_id, node_id)
    on delete cascade,
  foreign key (game_id, to_node_id)
    references graph_nodes(game_id, node_id)
    on delete cascade
);

create table if not exists game_progress (
  game_id text primary key,
  progress jsonb not null default '{}'::jsonb
);

create index if not exists graph_nodes_game_type_idx
  on graph_nodes(game_id, node_type);

create index if not exists graph_edges_game_type_idx
  on graph_edges(game_id, edge_type);

create index if not exists graph_edges_game_from_type_idx
  on graph_edges(game_id, from_node_id, edge_type);

create index if not exists graph_edges_game_to_type_idx
  on graph_edges(game_id, to_node_id, edge_type);
