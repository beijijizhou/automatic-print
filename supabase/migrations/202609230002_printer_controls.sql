alter table public.machine_commands
  drop constraint if exists machine_commands_action_check;

alter table public.machine_commands
  add constraint machine_commands_action_check
  check (action in ('download_layout', 'pause_print', 'clean_resume'));

comment on column public.machine_commands.action is
  'download/layout work or an explicit PrintExp pause/clean-resume control.';
