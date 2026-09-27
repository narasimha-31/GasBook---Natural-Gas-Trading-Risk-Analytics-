import { Header } from "./components/Header";
import { Intro } from "./chapters/Intro";
import { Prices } from "./chapters/Prices";
import { Risk } from "./chapters/Risk";

export default function App() {
  return (
    <>
      <Header />
      <main className="mx-auto max-w-6xl px-4 sm:px-6">
        <Intro />
        <Prices />
        <Risk />
      </main>
      <footer className="mx-auto max-w-6xl border-t border-rule px-4 py-10 text-sm text-ink-faint sm:px-6">
        GasBook · Real prices from EIA, CFTC, NYMEX and Open-Meteo. Trades, counterparties and confirmations are
        simulated.
      </footer>
    </>
  );
}
