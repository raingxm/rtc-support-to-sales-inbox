"use client";

import { useParams } from "next/navigation";
import { CustomerTicket } from "../../desk";

export default function Page() {
  const params = useParams<{ id: string | string[]; credential: string | string[] }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const credential = Array.isArray(params.credential) ? params.credential[0] : params.credential;

  return <CustomerTicket ticketId={id ?? ""} credential={credential ?? ""} />;
}
