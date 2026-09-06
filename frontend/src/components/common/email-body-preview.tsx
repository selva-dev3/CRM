const STRIPPED_CONTENT_PATTERN = /<(script|style)\b[^>]*>[\s\S]*?<\/\1\s*>/gi;
const COMMENT_PATTERN = /<!--[\s\S]*?-->/g;
const LINE_BREAK_PATTERN = /<br\s*\/?>/gi;
const LIST_ITEM_PATTERN = /<li\b[^>]*>/gi;
const BLOCK_END_PATTERN = /<\/(?:address|blockquote|div|h[1-6]|li|p|pre|section|table|tr)>/gi;
const TAG_PATTERN = /<[^>]+>/g;

const NAMED_ENTITIES: Readonly<Record<string, string>> = {
  amp: '&',
  apos: "'",
  gt: '>',
  lt: '<',
  nbsp: ' ',
  quot: '"',
};

function decodeEntity(entity: string): string {
  const normalized = entity.toLowerCase();
  if (normalized in NAMED_ENTITIES) return NAMED_ENTITIES[normalized];

  const isHex = normalized.startsWith('#x');
  const isDecimal = normalized.startsWith('#') && !isHex;
  if (!isHex && !isDecimal) return `&${entity};`;

  const codePoint = Number.parseInt(normalized.slice(isHex ? 2 : 1), isHex ? 16 : 10);
  if (!Number.isInteger(codePoint) || codePoint < 0 || codePoint > 0x10ffff) {
    return `&${entity};`;
  }

  try {
    return String.fromCodePoint(codePoint);
  } catch {
    return `&${entity};`;
  }
}

export function formatEmailBody(body: string | null | undefined): string {
  if (!body?.trim()) return 'No preview body.';

  const text = body
    .replace(STRIPPED_CONTENT_PATTERN, '')
    .replace(COMMENT_PATTERN, '')
    .replace(LINE_BREAK_PATTERN, '\n')
    .replace(LIST_ITEM_PATTERN, '• ')
    .replace(BLOCK_END_PATTERN, '\n')
    .replace(TAG_PATTERN, '')
    .replace(/&(#x[\da-f]+|#\d+|[a-z]+);/gi, (_match, entity: string) =>
      decodeEntity(entity),
    )
    .replace(/\r\n?/g, '\n')
    .split('\n')
    .map((line) => line.replace(/[\t ]+/g, ' ').trim())
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  return text || 'No preview body.';
}

interface EmailBodyPreviewProps {
  readonly body: string | null | undefined;
}

export function EmailBodyPreview({ body }: EmailBodyPreviewProps) {
  return (
    <p className="whitespace-pre-wrap break-words text-xs leading-5 text-slate-600">
      {formatEmailBody(body)}
    </p>
  );
}
