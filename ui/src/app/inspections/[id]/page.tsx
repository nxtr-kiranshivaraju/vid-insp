import { redirect } from "next/navigation";

export default function InspectionRoot({ params }: { params: { id: string } }) {
  redirect(`/inspections/${params.id}/intents`);
}
