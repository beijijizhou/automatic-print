alter table public.machine_status_current
  add column if not exists source_online boolean not null default true;

comment on column public.machine_status_current.source_online is
  'Whether the monitored status source, currently PrintExp, is running.';
