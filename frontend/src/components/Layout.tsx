import { NavLink, Outlet, useNavigate } from 'react-router'
import { useLogout, useMe } from '../api/hooks'
import { useI18n } from '../i18n'
import { cx } from './ui'

export function Logo() {
  return (
    <div className="flex items-center gap-2">
      <div className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-sm font-bold text-white shadow">
        M
      </div>
      <span className="text-lg font-semibold tracking-tight">MultiMind</span>
    </div>
  )
}

export function LanguageSwitch() {
  const { language, setLanguage } = useI18n()
  return (
    <div className="inline-flex rounded-lg bg-slate-100 p-0.5 text-xs font-medium">
      {(['pt', 'en'] as const).map((lang) => (
        <button
          key={lang}
          onClick={() => setLanguage(lang)}
          className={cx('rounded-md px-2 py-1 uppercase', language === lang ? 'bg-white shadow-sm' : 'text-slate-500')}
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
  const link = ({ isActive }: { isActive: boolean }) =>
    cx('rounded-lg px-3 py-1.5 text-sm font-medium', isActive ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:bg-slate-100')

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1600px] items-center gap-6 px-4">
          <NavLink to="/">
            <Logo />
          </NavLink>
          <nav className="flex items-center gap-1">
            <NavLink to="/" end className={link}>
              {t.nav.dashboard}
            </NavLink>
            <NavLink to="/agents" className={link}>
              {t.nav.agents}
            </NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <LanguageSwitch />
            <span className="hidden text-sm text-slate-500 sm:inline">{me?.display_name}</span>
            <button
              className="text-sm text-slate-500 hover:text-slate-800"
              onClick={() => logout.mutate(undefined, { onSuccess: () => navigate('/login') })}
            >
              {t.nav.logout}
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
