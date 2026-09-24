alter table public.machine_commands
  drop constraint if exists machine_commands_action_check;

alter table public.machine_commands
  add constraint machine_commands_action_check
  check (action in ('download_layout', 'start_print', 'pause_print', 'clean_resume'));
