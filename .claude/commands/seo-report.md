---
description: Run a full SEO audit + competitor analysis for any URL and save a named PDF report. Usage: /seo-report https://propertywebsite.com
---

Run a complete SEO report for: $ARGUMENTS

Follow these steps in order:

## Step 1 - Fetch property name
Fetch the URL $ARGUMENTS and extract the site title tag or H1. This is the property name used to name the PDF. If the title contains separators like | or - or :, use only the first part (e.g. "Acme Hotel" from "Acme Hotel | Official Site").

## Step 2 - Run full SEO audit
Run the complete /seo-audit skill on $ARGUMENTS covering all five categories and producing the SEO Health Index score 0-100 with full breakdown.

## Step 3 - Run competitor analysis
Run the complete seo-competitor skill on $ARGUMENTS. Identify top 3-5 competitors, audit each, produce the full comparison table, gap analysis, and competitive action plan.

## Step 4 - Generate PDF
Run this command to generate the named PDF report:
python audit.py $ARGUMENTS
The PDF saves automatically in backend/reports/ named after the property.

## Step 5 - Confirm
Tell the user the property name found, SEO Health Score and band, total issues by severity, exact PDF file path, and top 3 priority fixes.