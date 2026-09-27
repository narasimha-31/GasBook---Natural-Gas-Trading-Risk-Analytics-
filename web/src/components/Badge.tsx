/** Every chapter says plainly whether its numbers are real or simulated, as a stamp. */
export function Badge({ simulated }: { simulated: boolean }) {
  return simulated ? (
    <span className="stamp text-desk">Simulated book</span>
  ) : (
    <span className="stamp text-hedge">Real data</span>
  );
}
