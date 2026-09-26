create table if not exists public.machine_registry (
  machine_name text primary key check (machine_name ~ '^M([1-9]|1[01])$'),
  machine_id uuid not null unique,
  registered_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.machine_registry enable row level security;
revoke all on public.machine_registry from anon, authenticated;

-- Preserve only identities that are already unambiguous. Conflicting slots must be
-- claimed by a person from the desktop registration UI.
insert into public.machine_registry (machine_name, machine_id)
select machine_name, min(machine_id::text)::uuid
from public.machine_status_current
where machine_name ~ '^M([1-9]|1[01])$'
group by machine_name
having count(*) = 1
on conflict do nothing;

create or replace function public.register_machine_slot(
  p_machine_id uuid,
  p_machine_name text,
  p_replace boolean default false
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  occupant public.machine_registry%rowtype;
  registration public.machine_registry%rowtype;
  replaced jsonb := null;
begin
  if p_machine_name !~ '^M([1-9]|1[01])$' then
    raise exception '机器号必须是 M1-M11';
  end if;
  perform pg_advisory_xact_lock(hashtext(p_machine_name));
  select * into occupant from public.machine_registry
    where machine_name = p_machine_name for update;
  if occupant.machine_id is not null and occupant.machine_id <> p_machine_id then
    if not p_replace then
      raise exception '% 已由另一台电脑注册，需要人工确认换绑', p_machine_name;
    end if;
    replaced := to_jsonb(occupant);
    delete from public.machine_registry where machine_name = p_machine_name;
  end if;
  delete from public.machine_registry
    where machine_id = p_machine_id and machine_name <> p_machine_name;
  insert into public.machine_registry (machine_name, machine_id)
    values (p_machine_name, p_machine_id)
    on conflict (machine_name) do update set
      machine_id = excluded.machine_id,
      updated_at = now()
    returning * into registration;
  delete from public.machine_status_current
    where machine_name = p_machine_name and machine_id <> p_machine_id;
  update public.machine_status_current set
    machine_name = p_machine_name,
    updated_at = now()
    where machine_id = p_machine_id;
  return jsonb_build_object('registration', to_jsonb(registration), 'replaced', replaced);
end;
$$;

revoke all on function public.register_machine_slot(uuid, text, boolean)
  from public, anon, authenticated;
grant execute on function public.register_machine_slot(uuid, text, boolean)
  to service_role;
