import { DeskFrame } from "../../frame";

export default function Page() {
  return (
    <DeskFrame section="Customer">
      <main className="frame workspace">
        <div className="page-intro">
          <p className="eyebrow">Customer</p>
          <h1>This link does not open a ticket</h1>
          <p>A ticket number on its own is not the ticket address. Use the address you were given for this ticket.</p>
        </div>
      </main>
    </DeskFrame>
  );
}
