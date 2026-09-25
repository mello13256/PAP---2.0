import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router'
import { useLogin, useMe, useRegister } from '../api/hooks'
import { LanguageSwitch, Logo } from '../components/Layout'
import { Button, Card, ErrorBox, Field, Input } from '../components/ui'
import { useT } from '../i18n'

export function LoginPage() {
  const t = useT()
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

  return (
    <div className="flex min-h-full items-center justify-center bg-gradient-to-br from-slate-50 to-indigo-50 p-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-between">
          <Logo />
          <LanguageSwitch />
        </div>
        <p className="mb-4 text-sm text-slate-500">{t.app.tagline}</p>
        <Card className="p-6">
          <form onSubmit={submit} className="space-y-4">
            <h1 className="text-lg font-semibold">{mode === 'login' ? t.auth.login : t.auth.register}</h1>
            {mode === 'register' && (
              <Field label={t.auth.name}>
                <Input value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} />
              </Field>
            )}
            <Field label={t.auth.email}>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
            </Field>
            <Field label={t.auth.password} hint={mode === 'register' ? t.auth.passwordHint : undefined}>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={mode === 'register' ? 8 : 1}
              />
            </Field>
            {mutation.error && <ErrorBox error={mutation.error} />}
            <Button type="submit" className="w-full" loading={mutation.isPending}>
              {mode === 'login' ? t.auth.login : t.auth.register}
            </Button>
          </form>
          <p className="mt-4 text-center text-sm text-slate-500">
            {mode === 'login' ? t.auth.noAccount : t.auth.haveAccount}{' '}
            <button className="font-medium text-indigo-600" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
              {mode === 'login' ? t.auth.register : t.auth.login}
            </button>
          </p>
        </Card>
      </div>
    </div>
  )
}
