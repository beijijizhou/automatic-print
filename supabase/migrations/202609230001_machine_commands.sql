create table if not exists public.machine_commands (
  id uuid primary key default gen_random_uuid(),
  target_machine_id uuid not null,
  requested_by_machine_id uuid not null,
  requested_by_name text not null default '',
  action text not null check (action in ('download_layout')),
  payload jsonb not null default '{}'::jsonb
    check (jsonb_typeof(payload) = 'object'),
  status text not null default 'queued'
    check (status in ('queued', 'claimed', 'running', 'succeeded', 'failed', 'cancelled', 'expired')),
  phase text not null default '',
  progress_percent smallint check (progress_percent between 0 and 100),
  result jsonb not null default '{}'::jsonb
    check (jsonb_typeof(result) = 'object'),
  error_message text,
  expires_at timestamptz not null default (now() + interval '30 minutes'),
  claimed_at timestamptz,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  revision bigint not null default 1
);

comment on table public.machine_commands is
  'Short-lived commands claimed by one trusted Automatic Print machine.';

alter table public.machine_commands enable row level security;
revoke all on public.machine_commands from anon, authenticated;
alter table public.machine_commands replica identity full;

create index if not exists machine_commands_target_queue_idx
  on public.machine_commands (target_machine_id, status, created_at);
create index if not exists machine_commands_created_idx
  on public.machine_commands (created_at desc);

create or replace function public.claim_machine_command(target_id uuid)
returns setof public.machine_commands
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.machine_commands
  set status = 'expired', finished_at = now(), updated_at = now(),
      revision = revision + 1
  where target_machine_id = target_id
    and status = 'queued'
    and expires_at <= now();

  return query
  update public.machine_commands
  set status = 'claimed', claimed_at = now(), updated_at = now(),
      revision = revision + 1
  where id = (
    select id from public.machine_commands
    where target_machine_id = target_id
      and status = 'queued'
      and expires_at > now()
    order by created_at
    for update skip locked
    limit 1
  )
  returning *;
end;
$$;

revoke all on function public.claim_machine_command(uuid) from public;
grant execute on function public.claim_machine_command(uuid) to service_role;
