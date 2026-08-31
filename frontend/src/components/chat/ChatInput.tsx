import { useState, type FormEvent } from 'react'
import { Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface ChatInputProps {
  disabled: boolean
  onSend: (question: string) => void
}

export function ChatInput({ disabled, onSend }: ChatInputProps) {
  const [value, setValue] = useState('')

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2 px-8 py-4">
      <Input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        disabled={disabled}
        placeholder="Ask a question about the Enron corpus..."
        className="h-10 flex-1 rounded-full px-4"
      />
      <Button
        type="submit"
        size="icon-lg"
        className="rounded-full"
        disabled={disabled || !value.trim()}
        aria-label="Send"
      >
        <Send className="size-4" />
      </Button>
    </form>
  )
}
