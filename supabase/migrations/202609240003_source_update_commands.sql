alter table public.machine_commands
  drop constraint if exists machine_commands_action_check;

alter table public.machine_commands
  add constraint machine_commands_action_check
  check (action in (
    'download_layout', 'start_print', 'pause_print', 'clean_resume', 'probe',
    'source_update'
  ));

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
    and action in ('download_layout', 'source_update')
    and status = 'queued'
    and expires_at <= now();

  return query
  update public.machine_commands
  set status = 'claimed', claimed_at = now(), updated_at = now(),
      revision = revision + 1
  where id = (
    select id from public.machine_commands
    where target_machine_id = target_id
      and action in ('download_layout', 'source_update')
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
