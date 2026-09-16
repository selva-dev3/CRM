import type { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';
import {
  ArrowRight,
  BarChart3,
  Check,
  ChevronDown,
  Globe2,
  Menu,
  Play,
  Search,
  Trophy,
  UsersRound,
  Zap,
} from 'lucide-react';

export const metadata: Metadata = {
  title: 'Mivaro CRM | Turn leads into lasting relationships',
  description: 'Capture leads, stay on top of follow-ups, and build stronger customer relationships with Mivaro CRM.',
};

const navigation = [
  { label: 'Product', href: '#product' },
  { label: 'Solutions', href: '#solutions' },
  { label: 'Pricing', href: '#pricing' },
  { label: 'Resources', href: '#resources' },
  { label: 'About', href: '#about' },
] as const;

const benefits = [
  'Manage leads & customers',
  'Automate follow-ups',
  'Close deals faster',
  'Build stronger relationships',
] as const;

const journey = [
  { number: '01', label: 'Capture leads' },
  { number: '02', label: 'Connect with customers' },
  { number: '03', label: 'Move deals forward' },
  { number: '04', label: 'Track your progress' },
] as const;

const features = [
  { title: 'Capture Leads', description: 'Bring new opportunities into one organized workspace.', icon: UsersRound },
  { title: 'Automate Follow-ups', description: 'Keep the next conversation on your team’s radar.', icon: Zap },
  { title: 'Track Progress', description: 'See the work behind every customer relationship.', icon: BarChart3 },
  { title: 'Close More Deals', description: 'Move opportunities through a connected sales process.', icon: Trophy },
] as const;

function MivaroMark() {
  return (
    <svg className="landing-logo-mark" viewBox="0 0 56 48" fill="none" aria-hidden="true">
      <path d="M5 41 17.5 8c1.1-2.8 5-2.8 6.1 0L36 41" stroke="#0b6555" strokeWidth="8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M20 41 32.5 8c1.1-2.8 5-2.8 6.1 0L51 41" stroke="#16a994" strokeWidth="8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Brand() {
  return (
    <Link href="/" className="landing-brand" aria-label="Mivaro CRM home">
      <MivaroMark />
      <span className="landing-brand-text"><strong>Mivaro</strong><span>CRM</span></span>
    </Link>
  );
}

export default function LandingPage() {
  return (
    <main className="landing-page">
      <div className="landing-hero-shell">
        <header className="landing-header">
          <div className="landing-header-inner">
            <Brand />
            <nav className="landing-nav" aria-label="Primary navigation">
              {navigation.map((item) => <a key={item.label} href={item.href}>{item.label}</a>)}
            </nav>
            <div className="landing-header-actions">
              <a href="#product" className="landing-header-icon" aria-label="Explore product features"><Search size={21} strokeWidth={1.9} /></a>
              <span className="landing-language" aria-label="Page language: English"><Globe2 size={20} strokeWidth={1.8} /> EN <ChevronDown size={13} /></span>
              <Link href="/login" className="landing-sign-in">Sign in</Link>
              <Link href="/register" className="landing-header-cta">Get Started <ArrowRight size={17} /></Link>
            </div>
            <details className="landing-mobile-nav">
              <summary aria-label="Open navigation menu"><Menu size={23} /></summary>
              <nav aria-label="Mobile navigation">
                {navigation.map((item) => <a key={item.label} href={item.href}>{item.label}</a>)}
                <Link href="/login">Sign in</Link>
                <Link href="/register">Get Started</Link>
              </nav>
            </details>
          </div>
        </header>

        <section className="landing-hero" aria-labelledby="landing-title">
          <div className="landing-hero-copy">
            <p className="landing-eyebrow"><span aria-hidden="true" /> CRM for Growing Businesses</p>
            <h1 id="landing-title">Turn Leads into <span>Lasting Relationships</span></h1>
            <p className="landing-hero-description">Mivaro CRM helps you capture, track, and convert more leads with a simple, powerful, and intelligent platform.</p>
            <div className="landing-hero-actions">
              <Link href="/register" className="landing-primary-button">Get Started <ArrowRight size={18} /></Link>
              <a href="/landing/landingbackground1.jpeg" target="_blank" rel="noopener noreferrer" className="landing-secondary-button"><span><Play size={13} fill="currentColor" /></span> View CRM Preview</a>
            </div>
            <ul className="landing-benefits">
              {benefits.map((benefit) => <li key={benefit}><span className="landing-benefit-check"><Check size={13} strokeWidth={2.4} /></span>{benefit}</li>)}
            </ul>
            <div className="landing-journey" aria-label="The Mivaro CRM workflow">
              {journey.map((step) => <div key={step.number}><strong>{step.number}</strong><span>{step.label}</span></div>)}
            </div>
          </div>

          <div className="landing-hero-visual" id="product-preview">
            <div className="landing-preview-frame">
              <Image
                src="/landing/landingbackground1.jpeg"
                alt="Mivaro CRM preview showing a leads dashboard with search, metrics, and customer records"
                fill
                priority
                sizes="(max-width: 760px) 94vw, (max-width: 1120px) 88vw, 52vw"
                className="landing-preview-image"
              />
            </div>
          </div>
          <p className="landing-script" aria-hidden="true">Grow.<br />Connect.<br />Succeed.</p>
        </section>
      </div>

      <section className="landing-trust-band" aria-label="Connected CRM capabilities">
        <p>One place for the work that moves your business forward</p>
        <div className="landing-capabilities" aria-hidden="true">
          <span>LEADS</span><span>CONTACTS</span><span>DEALS</span><span>PROJECTS</span><span>SUPPORT</span><span>INSIGHTS</span>
        </div>
      </section>

      <section className="landing-feature-strip" id="product" aria-label="Product features">
        {features.map(({ title, description, icon: Icon }) => (
          <article key={title} className="landing-feature">
            <div className="landing-feature-icon"><Icon size={29} strokeWidth={2.4} aria-hidden="true" /></div>
            <div><h2>{title}</h2><p>{description}</p></div>
          </article>
        ))}
      </section>

      <section className="landing-below-fold" id="solutions">
        <div>
          <p className="landing-section-kicker">BUILT TO STAY CONNECTED</p>
          <h2>From first conversation to the next opportunity.</h2>
          <p>Keep your people, conversations, and sales work together in one CRM workspace.</p>
        </div>
        <div className="landing-below-fold-links">
          <a href="#product-preview">Explore the CRM preview <ArrowRight size={17} /></a>
          <Link href="/register">Create your workspace <ArrowRight size={17} /></Link>
        </div>
      </section>

      <footer className="landing-footer">
        <div id="about"><Brand /><p>Customer relationships, made easier to manage.</p></div>
        <div id="pricing"><h2>Pricing</h2><p>Find the right setup for your team when you get started.</p><Link href="/register">Get Started <ArrowRight size={15} /></Link></div>
        <div id="resources"><h2>Resources</h2><p>Explore the product preview or sign in to your workspace.</p><a href="#product-preview">Product preview <ArrowRight size={15} /></a></div>
      </footer>
    </main>
  );
}
