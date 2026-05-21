import { Suspense } from "react";

import { OpportunityReviewWorkbench } from "@/components/OpportunityReviewWorkbench";

export default function OpportunitiesPage() {
  return (
    <Suspense fallback={<div className="card text-sm text-slate-600">Loading opportunities...</div>}>
      <OpportunityReviewWorkbench />
    </Suspense>
  );
}
