-- t1ld3 sync schema. Paste into the Supabase SQL editor and run once.
--
-- Everything a user syncs lives in one table: to-dos, calendar events,
-- settings, launcher commands and their profile. Each row is one record
-- of a kind, holding its fields as JSON.

create table if not exists public.items (
  user_id uuid not null default auth.uid()
    references auth.users (id) on delete cascade,
  kind text not null
    check (kind in ('task', 'event', 'setting', 'commands', 'profile')),
  id text not null,
  data jsonb not null default '{}'::jsonb,
  -- Deleted records are kept as tombstones so the deletion syncs too.
  deleted boolean not null default false,
  -- When the edit was made, by the editing device's clock.
  updated_at timestamptz not null,
  -- When the server stored it; devices pull everything newer than the
  -- last value they saw. Set by the trigger below, never by clients.
  server_updated_at timestamptz not null default now(),
  primary key (user_id, kind, id)
);

create index if not exists items_user_server_updated_at
  on public.items (user_id, server_updated_at);

-- Last write wins: an edit that arrives late (say from a laptop that was
-- offline) can't overwrite a newer one.
create or replace function public.items_before_write()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'UPDATE' and new.updated_at < old.updated_at then
    return old;
  end if;
  new.server_updated_at := now();
  return new;
end;
$$;

drop trigger if exists items_before_write on public.items;
create trigger items_before_write
  before insert or update on public.items
  for each row execute function public.items_before_write();

-- Each signed-in user sees and changes only their own rows.
alter table public.items enable row level security;

drop policy if exists "Users manage their own items" on public.items;
create policy "Users manage their own items"
  on public.items
  for all
  to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

revoke all on public.items from anon;
grant select, insert, update, delete on public.items to authenticated;
