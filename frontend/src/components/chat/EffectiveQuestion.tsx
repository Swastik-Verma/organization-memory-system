interface EffectiveQuestionProps {
  text: string
}

export function EffectiveQuestion({ text }: EffectiveQuestionProps) {
  return (
    <p className="mb-1.5 text-xs text-muted-foreground">
      Interpreted as: <span className="italic">{text}</span>
    </p>
  )
}
