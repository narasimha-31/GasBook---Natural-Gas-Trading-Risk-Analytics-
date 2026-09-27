import { Header } from "./components/Header";
import { Context } from "./chapters/Context";
import { Desk } from "./chapters/Desk";
import { Intro } from "./chapters/Intro";
import { Method } from "./chapters/Method";
import { Hedges } from "./chapters/Hedges";
import { Prices } from "./chapters/Prices";
import { Risk } from "./chapters/Risk";
import { Signals } from "./chapters/Signals";
import { Weather } from "./chapters/Weather";

export default function App() {
  return (
    <>
      <Header />
      <main className="mx-auto max-w-6xl px-4 sm:px-6">
        <Intro />
        <Prices />
        <Risk />
        <Hedges />
        <Signals />
        <Weather />
        <Desk />
        <Context />
        <Method />
      </main>
      <footer className="mx-auto max-w-6xl border-t border-rule px-4 py-10 text-sm text-ink-faint sm:px-6">
        GasBook · Real prices from EIA, CFTC, NYMEX and Open-Meteo. Trades, counterparties and confirmations are
        simulated.
      </footer>
    </>
  );
}
