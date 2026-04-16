# Backlink Quality Scoring Methodology

## Toxic Link Indicators (30 Patterns)

### Definite Spam (auto-flag)
1. Link from domain with 10,000+ outbound links per page
2. Link from domain with no indexed pages in Google
3. Link from domain registered <30 days ago with 100+ outbound links
4. Exact-match anchor text from 5+ unrelated domains
5. Links from doorway pages (thin content, keyword-stuffed)
6. Links from hacked sites (pharma/casino injections)
7. Links from known link networks (check against known PBN lists)
8. Footer/sidebar site-wide links from unrelated domains
9. Links from auto-generated content (spun articles)
10. Links from domains with manual Google penalties

### Likely Spam (manual review)
11. Links from domains with >90% outbound link ratio
12. Foreign-language domains linking to English content (and vice versa)
13. Links from expired/auctioned domains repurposed for link building
14. Links from pages with >50 outbound links
15. Links from sites with no real traffic (parked domains)
16. Reciprocal link patterns across 10+ domains
17. Links from Web 2.0 properties with thin content
18. Links from article directories (EzineArticles, ArticleBase)
19. Links from low-quality guest post networks
20. Links from unrelated niches (e.g., pet site linking to SaaS)

### Potentially Problematic (monitor)
21. Links from social bookmarking sites at scale
22. Links from forum profiles (not discussions)
23. Links from press release syndication networks
24. Links from coupon/deal aggregators
25. Links from generic directories (not industry-specific)
26. Links with hidden/invisible anchor text
27. Links from pages with cloaked content
28. Links from sites with thin affiliate content
29. Links from comment sections without editorial context
30. Links from nofollow-only domains (limited SEO value)

## Anchor Text Ratio Benchmarks by Industry

| Industry | Branded | URL | Generic | Exact Match | Partial Match |
|----------|---------|-----|---------|-------------|---------------|
| SaaS | 40-55% | 15-20% | 10-15% | 3-8% | 10-15% |
| E-commerce | 35-45% | 15-25% | 10-15% | 5-10% | 10-20% |
| Local Service | 45-60% | 10-15% | 15-20% | 5-10% | 5-10% |
| Publisher/Blog | 30-40% | 20-30% | 10-15% | 3-8% | 10-20% |
| Agency | 40-50% | 15-20% | 10-15% | 5-10% | 10-15% |

## Link Velocity Red Flags

| Pattern | Signal | Action |
|---------|--------|--------|
| 10x normal new links in 1 week | Possible negative SEO | Investigate source, prepare disavow |
| 50%+ links lost in 1 month | Penalty or site issues | Check GSC for manual actions |
| Zero new links for 3+ months | Content not attracting links | Review content strategy |
| All new links from same TLD | Coordinated link building | Diversify sources |
| Spike from single country | Link network activity | Review geographic sources |

## Disavow Recommendations

**When to disavow:**
- Domain has received a manual penalty from Google
- Clear evidence of negative SEO attack
- Toxic link ratio exceeds 10% of total profile
- Specific domains identified as PBN or link farms

**When NOT to disavow:**
- Low-quality links that Google likely ignores anyway
- Nofollow links (already devalued by Google)
- Links from legitimate but low-authority sites
- Small number of spam links (<2% of profile)

**Disavow file format:**
```
# Toxic domains identified by Claude SEO backlink analysis
# Date: YYYY-MM-DD
# Total domains disavowed: X
domain:spamsite1.com
domain:linkfarm2.net
domain:pbn-network3.xyz
```
