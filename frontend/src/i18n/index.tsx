import { createContext, useContext, useState, type ReactNode } from 'react'
import { en } from './en'
import { pt, type Dictionary } from './pt'

export type Language = 'pt' | 'en'
const dictionaries: Record<Language, Dictionary> = { pt, en }
const STORAGE_KEY = 'multimind.language'

function initialLanguage(): Language {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'pt' || saved === 'en') return saved
  } catch {
    /* armazenamento indisponível: usa o idioma do browser */
  }
  return navigator.language?.toLowerCase().startsWith('pt') ? 'pt' : 'en'
}

interface I18nValue {
  t: Dictionary
  language: Language
  setLanguage: (language: Language) => void
}

const I18nContext = createContext<I18nValue | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(initialLanguage)
  const setLanguage = (next: Language) => {
    setLanguageState(next)
    document.documentElement.lang = next
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      /* ignora */
    }
  }
  return (
    <I18nContext.Provider value={{ t: dictionaries[language], language, setLanguage }}>
      {children}
    </I18nContext.Provider>
  )
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext)
  if (!value) throw new Error('useI18n fora do I18nProvider')
  return value
}

export const useT = () => useI18n().t
