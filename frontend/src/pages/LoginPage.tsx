import { Bot, GitCompare, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router'
import { useLogin, useMe, useRegister } from '../api/hooks'
import { LanguageSwitch, Logo } from '../components/Layout'
import { Button, ErrorBox, Field, Input } from '../components/ui'
import { useI18n } from '../i18n'

export function LoginPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { data: me } = useMe()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const login = useLogin()
  const register = useRegister()
  const mutation = mode === 'login' ? login : register

  if (me) return <Navigate to="/" replace />

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const done = { onSuccess: () => navigate('/') }
    if (mode === 'login') login.mutate({ email, password }, done)
    else register.mutate({ email, password, display_name: name }, done)
  }

  const features = [
    { icon: Bot, text: t.home.heroText },
    { icon: GitCompare, text: t.modelsPage.needsInternet },
    { icon: ShieldCheck, text: t.modelsPage.subtitle },
  ]

  return (
    <div className="grid min-h-full lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-slate-950 bg-gradient-to-br from-slate-950 via-indigo-950 to-violet-900 p-12 text-white lg:flex lg:flex-col">
        <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-fuchsia-500/20 blur-3xl" />
        <div className="absolute -bottom-32 -left-16 h-96 w-96 rounded-full bg-indigo-500/20 blur-3xl" />
        <Logo light />
        <div className="relative mt-auto max-w-lg">
          <h1 className="text-4xl font-semibold leading-tight tracking-tight">{t.home.heroTitle}</h1>
          <ul className="mt-8 space-y-4">
            {features.map(({ icon: Icon, text }) => (
              <li key={text} className="flex gap-3 text-sm text-indigo-100/90">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white/10"><Icon className="h-4 w-4" /></span>
                <span className="pt-1.5">{text}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center justify-between">
            <div className="lg:invisible"><Logo /></div>
            <LanguageSwitch />
          </div>
          <h2 className="text-2xl font-semibold tracking-tight">{mode === 'login' ? t.auth.login : t.auth.register}</h2>
          <p className="mt-1 text-sm text-slate-500">{t.app.tagline}</p>
          <form onSubmit={submit} className="mt-6 space-y-4">
            {mode === 'register' && (
              <Field label={t.auth.name}>
                <Input value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} />
              </Field>
            )}
            <Field label={t.auth.email}>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
            </Field>
            <Field label={t.auth.password} hint={mode === 'register' ? t.auth.passwordHint : undefined}>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={mode === 'register' ? 8 : 1} />
            </Field>
            {mutation.error && <ErrorBox error={mutation.error} />}
            <Button type="submit" className="w-full py-2.5" loading={mutation.isPending}>
              {mode === 'login' ? t.auth.login : t.auth.register}
            </Button>
          </form>
          <p className="mt-6 text-center text-sm text-slate-500">
            {mode === 'login' ? t.auth.noAccount : t.auth.haveAccount}{' '}
            <button className="font-medium text-indigo-600 hover:text-indigo-500" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
              {mode === 'login' ? t.auth.register : t.auth.login}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
