

from __future__ import annotations
from  analyzer import CompanyProfile


class RAGContextBuilder:
    """
    Produces a prompt-ready context block comparing the client company
    against its competitors across every constraint category.
    """

    def build(
        self,
        client: CompanyProfile,
        competitors: list[CompanyProfile],
    ) -> str:
        lines: list[str] = []
        lines.append("=== EdTech Competitive Intelligence Report ===")
        lines.append(f"Client Company : {client.name}  |  Domain: {client.domain}")
        lines.append(f"Overall Score  : {client.overall_score:.1f}/100")
        lines.append(f"Student Intake Δ: {client.student_intake_change_pct:+.1f}%")
        lines.append("")

        for comp in competitors:
            lines.append(f"--- Competitor: {comp.name} ---")
            lines.append(f"  Overall Score     : {comp.overall_score:.1f}/100")
            lines.append(f"  Student Intake Δ  : {comp.student_intake_change_pct:+.1f}%")
            lines.append(self._pricing_ctx(client, comp))
            lines.append(self._course_ctx(client, comp))
            lines.append(self._engagement_ctx(client, comp))
            lines.append(self._retention_ctx(client, comp))
            lines.append("")

        lines.append(self._industry_averages(competitors))
        return "\n".join(lines)

    # ── Section builders ──────────────────────────────────

    def _pricing_ctx(self, c: CompanyProfile, comp: CompanyProfile) -> str:
        gap = comp.pricing.base_price - c.pricing.base_price
        disc_gap = comp.pricing.discount_pct - c.pricing.discount_pct
        return (
            f"  PRICING:\n"
            f"    Client base price   = ₹{c.pricing.base_price:,.0f}  "
            f"| Competitor = ₹{comp.pricing.base_price:,.0f}  (gap {gap:+,.0f})\n"
            f"    Client discount     = {c.pricing.discount_pct:.0f}%  "
            f"| Competitor = {comp.pricing.discount_pct:.0f}%  (gap {disc_gap:+.0f}pp)\n"
            f"    Client EMI          = {c.pricing.has_emi}  "
            f"| Competitor = {comp.pricing.has_emi}\n"
            f"    Client free ratio   = {c.pricing.free_paid_ratio:.0%}  "
            f"| Competitor = {comp.pricing.free_paid_ratio:.0%}\n"
            f"    Client price Δ      = {c.pricing.price_change_pct:+.1f}%  "
            f"| Competitor Δ = {comp.pricing.price_change_pct:+.1f}%\n"
            f"    Pricing Score — Client: {c.pricing.score:.1f}  "
            f"| Competitor: {comp.pricing.score:.1f}"
        )

    def _course_ctx(self, c: CompanyProfile, comp: CompanyProfile) -> str:
        return (
            f"  COURSES:\n"
            f"    Duration (weeks)    = {c.courses.avg_duration_weeks:.1f} vs {comp.courses.avg_duration_weeks:.1f}\n"
            f"    Modules             = {c.courses.num_modules} vs {comp.courses.num_modules}\n"
            f"    Certification       = {c.courses.has_certification} vs {comp.courses.has_certification}\n"
            f"    Live ratio          = {c.courses.live_ratio:.0%} vs {comp.courses.live_ratio:.0%}\n"
            f"    Doubt solving       = {c.courses.has_doubt_solving} vs {comp.courses.has_doubt_solving}\n"
            f"    Assignments         = {c.courses.has_assignments} vs {comp.courses.has_assignments}\n"
            f"    Beginner ratio      = {c.courses.beginner_ratio:.0%} vs {comp.courses.beginner_ratio:.0%}\n"
            f"    Popular courses     = {', '.join(c.courses.popular_courses) or 'N/A'}\n"
            f"    Course Score — Client: {c.courses.score:.1f}  | Competitor: {comp.courses.score:.1f}"
        )

    def _engagement_ctx(self, c: CompanyProfile, comp: CompanyProfile) -> str:
        return (
            f"  ENGAGEMENT:\n"
            f"    Ads/week            = {c.engagement.ads_frequency_weekly:.1f} vs {comp.engagement.ads_frequency_weekly:.1f}\n"
            f"    Social posts/week   = {c.engagement.social_posts_weekly:.1f} vs {comp.engagement.social_posts_weekly:.1f}\n"
            f"    YT videos/month     = {c.engagement.youtube_videos_monthly:.1f} vs {comp.engagement.youtube_videos_monthly:.1f}\n"
            f"    YT avg views        = {c.engagement.youtube_avg_views:,.0f} vs {comp.engagement.youtube_avg_views:,.0f}\n"
            f"    Review rating       = {c.engagement.review_rating:.1f} vs {comp.engagement.review_rating:.1f}\n"
            f"    Students enrolled   = {c.engagement.students_enrolled:,} vs {comp.engagement.students_enrolled:,}\n"
            f"    Engagement Score — Client: {c.engagement.score:.1f}  | Competitor: {comp.engagement.score:.1f}"
        )

    def _retention_ctx(self, c: CompanyProfile, comp: CompanyProfile) -> str:
        return (
            f"  RETENTION:\n"
            f"    Referral program    = {c.retention.referral_program} vs {comp.retention.referral_program}\n"
            f"    Rewards offered     = {c.retention.rewards_offered} vs {comp.retention.rewards_offered}\n"
            f"    Free trial          = {c.retention.free_trial} vs {comp.retention.free_trial}\n"
            f"    Website changes     = {c.retention.website_changes_count} vs {comp.retention.website_changes_count}\n"
            f"    Discontinuity sigs  = {c.retention.discontinuity_signals} vs {comp.retention.discontinuity_signals}\n"
            f"    Retention Score — Client: {c.retention.score:.1f}  | Competitor: {comp.retention.score:.1f}"
        )

    def _industry_averages(self, competitors: list[CompanyProfile]) -> str:
        if not competitors:
            return ""
        def avg(vals):
            return sum(vals) / len(vals)

        return (
            "=== Industry Averages (competitors) ===\n"
            f"  Overall score       : {avg([c.overall_score for c in competitors]):.1f}\n"
            f"  Pricing score       : {avg([c.pricing.score for c in competitors]):.1f}\n"
            f"  Course score        : {avg([c.courses.score for c in competitors]):.1f}\n"
            f"  Engagement score    : {avg([c.engagement.score for c in competitors]):.1f}\n"
            f"  Retention score     : {avg([c.retention.score for c in competitors]):.1f}\n"
            f"  Avg intake Δ        : {avg([c.student_intake_change_pct for c in competitors]):+.1f}%"
        )

