alter table public.machine_status_current
  add column if not exists availability_override text not null default 'auto'
    check (availability_override in ('auto', 'available', 'unavailable')),
  add column if not exists auto_available boolean not null default true,
  add column if not exists availability_reason text not null default '',
  add column if not exists last_feedback_at timestamptz;

update public.machine_status_current
set last_feedback_at = coalesce(last_feedback_at, heartbeat_at, updated_at, now());

comment on column public.machine_status_current.availability_override is
  'Shared manual override: auto, available, or unavailable.';
comment on column public.machine_status_current.auto_available is
  'Event-driven availability. False after a command receives no acknowledgement.';
comment on column public.machine_status_current.last_feedback_at is
  'Last startup, state change, command claim, or command result; no periodic heartbeat.';
