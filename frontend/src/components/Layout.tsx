import { Bot, Cpu, LayoutDashboard, LogOut } from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router'
import { useLogout, useMe } from '../api/hooks'
import { useI18n } from '../i18n'
import { cx } from './ui'

export function Logo({ light }: { light?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="relative grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-indigo-500 via-violet-500 to-fuchsia-500 shadow-lg shadow-indigo-500/30">
        <svg viewBox="0 0 24 24" className="h-5 w-5 text-white" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
          <circle cx="6" cy="7" r="2.2" />
          <circle cx="18" cy="7" r="2.2" />
          <circle cx="12" cy="17" r="2.2" />
          <path d="M8 8.2 10.8 15M16 8.2 13.2 15M8.2 7h7.6" />
        </svg>
      </div>
      <span className={cx('text-lg font-semibold tracking-tight', light ? 'text-white' : 'text-slate-900')}>MultiMind</span>
    </div>
  )
}

export function LanguageSwitch({ dark }: { dark?: boolean }) {
  const { language, setLanguage } = useI18n()
  return (
    <div className={cx('inline-flex rounded-lg p-0.5 text-xs font-medium', dark ? 'bg-white/10' : 'bg-slate-100')}>
      {(['pt', 'en'] as const).map((lang) => (
        <button
          key={lang}
          onClick={() => setLanguage(lang)}
          className={cx(
            'rounded-md px-2 py-1 uppercase transition',
            language === lang ? (dark ? 'bg-white text-slate-900' : 'bg-white shadow-sm') : dark ? 'text-slate-300 hover:text-white' : 'text-slate-500',
          )}
        >
          {lang}
        </button>
      ))}
    </div>
  )
}

export function Layout() {
  const { t } = useI18n()
  const { data: me } = useMe()
  const logout = useLogout()
  const navigate = useNavigate()
  const items = [
    { to: '/', label: t.nav.dashboard, icon: LayoutDashboard, end: true },
    { to: '/models', label: t.nav.models, icon: Cpu },
    { to: '/agents', label: t.nav.agents, icon: Bot },
  ]

  return (
    <div className="flex min-h-full">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col bg-slate-950 bg-gradient-to-b from-slate-950 via-slate-900 to-indigo-950 px-3 py-5 text-slate-300 lg:flex">
        <div className="px-2">
          <Logo light />
        </div>
        <nav className="mt-8 flex flex-col gap-1">
          {items.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cx(
                  'flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition',
                  isActive ? 'bg-white/10 text-white shadow-inner' : 'hover:bg-white/5 hover:text-white',
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto space-y-3 border-t border-white/10 px-2 pt-4">
          <LanguageSwitch dark />
          <div className="flex items-center gap-2">
            <div className="grid h-8 w-8 place-items-center rounded-full bg-white/10 text-xs font-semibold text-white">
              {me?.display_name?.slice(0, 1).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm text-white">{me?.display_name}</div>
              <div className="truncate text-xs text-slate-400">{me?.email}</div>
            </div>
            <button
              title={t.nav.logout}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-white"
              onClick={() => logout.mutate(undefined, { onSuccess: () => navigate('/login') })}
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Barra superior em ecrãs pequenos */}
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-slate-200 bg-white/90 px-4 py-2.5 backdrop-blur lg:hidden">
          <Logo />
          <nav className="ml-auto flex items-center gap-1">
            {items.map(({ to, icon: Icon, end, label }) => (
              <NavLink key={to} to={to} end={end} title={label} className={({ isActive }) => cx('rounded-lg p-2', isActive ? 'bg-indigo-50 text-indigo-600' : 'text-slate-500')}>
                <Icon className="h-4 w-4" />
              </NavLink>
            ))}
          </nav>
          <LanguageSwitch />
        </header>
        <main className="mx-auto w-full max-w-[1500px] flex-1 px-4 py-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
