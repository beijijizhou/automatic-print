create table if not exists public.machine_status_current (
  machine_id uuid primary key,
  machine_name text not null check (char_length(machine_name) between 1 and 100),
  department text not null default 'DTF'
    check (department in ('DTF', 'UV', '3D')),
  state text not null
    check (state in ('idle', 'running', 'completed', 'failed', 'stopped')),
  phase text not null default '',
  progress_percent smallint check (progress_percent between 0 and 100),
  batch_id text,
  batch_name text,
  batch_info jsonb not null default '{}'::jsonb
    check (jsonb_typeof(batch_info) = 'object'),
  remaining_seconds integer check (remaining_seconds >= 0),
  estimate_scope text check (estimate_scope in ('phase', 'batch')),
  estimated_finish_at timestamptz,
  started_at timestamptz,
  heartbeat_at timestamptz not null default now(),
  app_version text not null default '',
  error_message text,
  revision bigint not null default 1,
  updated_at timestamptz not null default now()
);

comment on table public.machine_status_current is
  'Latest trusted heartbeat for each Automatic Print installation.';
comment on column public.machine_status_current.remaining_seconds is
  'Null means no reliable estimate; estimate_scope states whether ETA is for the phase or batch.';

alter table public.machine_status_current enable row level security;
revoke all on public.machine_status_current from anon, authenticated;
alter table public.machine_status_current replica identity full;

do $$
begin
  alter publication supabase_realtime add table public.machine_status_current;
exception
  when duplicate_object then null;
end $$;

create index if not exists machine_status_current_heartbeat_idx
  on public.machine_status_current (heartbeat_at desc);
