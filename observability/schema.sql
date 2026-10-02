-- AgriMind observability schema — Supabase PostgreSQL (canonical, Section 5 of the doc)
-- Run this in the Supabase SQL editor to provision the observability layer.

create table if not exists agent_logs (
    id          bigserial primary key,
    run_id      uuid not null,
    agent_name  text not null,
    input       jsonb,
    output      jsonb,
    status      text,
    confidence  double precision,
    latency     double precision,
    timestamp   timestamptz not null default now()
);
create index if not exists idx_agent_logs_run_id on agent_logs(run_id);

create table if not exists decisions (
    decision_id bigserial primary key,
    run_id      uuid not null,
    recommendation text,
    reason      text,
    confidence  double precision,
    timestamp   timestamptz not null default now()
);
create index if not exists idx_decisions_run_id on decisions(run_id);

create table if not exists conflicts (
    conflict_id bigserial primary key,
    run_id      uuid not null,
    agent_a     text,
    agent_b     text,
    issue       text,
    resolution  text,
    priority    integer
);
create index if not exists idx_conflicts_run_id on conflicts(run_id);

create table if not exists feedback (
    id                  bigserial primary key,
    run_id              uuid not null,
    farmer_action_taken text,
    outcome_reported    text,
    comment             text,
    timestamp           timestamptz not null default now()
);
create index if not exists idx_feedback_run_id on feedback(run_id);

-- Row-level security: enable and restrict per-farmer access once auth is wired in.
-- Left permissive for the prototype; tighten before any real deployment
-- (flagged for the Codex Security review pass in the build orchestration prompt).
alter table agent_logs enable row level security;
alter table decisions enable row level security;
alter table conflicts enable row level security;
alter table feedback enable row level security;

create policy "prototype_allow_all_agent_logs" on agent_logs for all using (true);
create policy "prototype_allow_all_decisions" on decisions for all using (true);
create policy "prototype_allow_all_conflicts" on conflicts for all using (true);
create policy "prototype_allow_all_feedback" on feedback for all using (true);
