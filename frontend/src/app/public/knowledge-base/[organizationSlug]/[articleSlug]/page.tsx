import { notFound } from 'next/navigation';

import { resolveApiBaseUrl } from '@/lib/api/client';

interface Article { title:string; summary:string|null; body:string; category:string|null; published_at:string|null }

export default async function PublicKnowledgeArticlePage({params}:{params:Promise<{organizationSlug:string;articleSlug:string}>}){const{organizationSlug,articleSlug}=await params;const response=await fetch(`${resolveApiBaseUrl()}/public/knowledge-base/${encodeURIComponent(organizationSlug)}/${encodeURIComponent(articleSlug)}`,{next:{revalidate:300}});if(!response.ok)notFound();const article=await response.json() as Article;return <main className="mx-auto min-h-screen max-w-3xl px-5 py-12"><article className="rounded-2xl border bg-white p-6 shadow-sm sm:p-10"><p className="text-sm font-semibold text-indigo-600">{article.category||'Knowledge Base'}</p><h1 className="mt-2 text-3xl font-bold text-slate-900">{article.title}</h1>{article.summary&&<p className="mt-4 text-lg text-slate-600">{article.summary}</p>}<div className="mt-8 whitespace-pre-wrap text-slate-800">{article.body}</div></article></main>}
