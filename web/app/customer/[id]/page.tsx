"use client";

import { useParams } from "next/navigation";
import { CustomerTicket } from "../desk";

export default function Page() {
  const params = useParams<{ id: string | string[] }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;

  return <CustomerTicket ticketId={id ?? ""} />;
}
