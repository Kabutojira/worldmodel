#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import os
import re
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / '.worldmodel' / 'entity_seed_batch.csv'
TODAY = dt.date.today().isoformat()
NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
YEAR = str(dt.date.today().year)

ENTITIES_HEADER = [
    'entity_id','slug','name','type','status','priority','ticker','exchange','currency','geography','sector','industry','business_lines','description','search_keywords','connected_entities','last_retrieval_at','last_report_date','last_source_count','confidence','owner_notes'
]
RELATIONSHIPS_HEADER = [
    'source_slug','target_slug','relationship_type','direction','importance','mechanism','why_connected','evidence_url','last_reviewed_at','confidence'
]
ESTIMATES_HEADER = [
    'entity_slug','entity_name','type','business_line','metric','unit','currency','actual_or_estimate','year','base_value','bearish_forecast','normal_forecast','bullish_forecast','bearish_thesis','normal_thesis','bullish_thesis','source_url','source_date','updated_at','confidence','notes'
]
SOURCE_LOG_HEADER = [
    'source_id','entity_slug','title','source_name','source_type','url','author','published_at','retrieved_at','quality_score','recency_score','relevance_score','used_in_update','summary_path','hash','notes'
]

PRIORITY_MAP = {'P0': '1', 'P1': '2', 'P2': '3'}
STATUS_MAP = {'P0': 'active', 'P1': 'active', 'P2': 'paused'}

PUBLIC_TICKERS = {
    'tesla': 'TSLA', 'nvidia': 'NVDA', 'tsmc': 'TSM', 'asml': 'ASML', 'amd': 'AMD', 'broadcom': 'AVGO', 'arm': 'ARM', 'micron': 'MU',
    'sk_hynix': '000660.KS', 'samsung_electronics': '005930.KS', 'intel': 'INTC', 'cadence': 'CDNS', 'synopsys': 'SNPS', 'google': 'GOOGL',
    'meta': 'META', 'amazon': 'AMZN', 'aws': 'AMZN', 'microsoft': 'MSFT', 'oracle': 'ORCL', 'apple': 'AAPL', 'waymo': 'GOOGL', 'byd': '1211.HK',
    'toyota': '7203.T', 'volkswagen': 'VOW3.DE', 'catl': '300750.SZ', 'panasonic_energy': '6752.T', 'lg_energy_solution': '373220.KS',
    'samsung_sdi': '006400.KS', 'albemarle': 'ALB', 'sqm': 'SQM', 'fanuc': '6954.T', 'abb_robotics': 'ABBN.SW', 'rockwell_automation': 'ROK',
    'siemens': 'SIEGY', 'rocket_lab': 'RKLB'
}

DISPLAY_OVERRIDES = {
    'aws': 'AWS', 'xai': 'xAI', 'tsmc': 'TSMC', 'asml': 'ASML', 'sk_hynix': 'SK hynix', 'ev_market': 'EV market',
    'battery_storage': 'Battery energy storage', 'robotaxi_autonomy': 'Robotaxi and autonomy', 'humanoid_robots': 'Humanoid robots',
    'electricity_grid': 'Electricity grid', 'cloud_market': 'Cloud infrastructure market', 'digital_ads': 'Digital advertising market',
    'vr_ar_market': 'VR/AR market', 'ai_agents': 'AI agents', 'ai_inference_economics': 'AI inference economics',
    'ai_consumer_devices': 'AI consumer devices', 'us_china_chip_controls': 'US-China chip controls',
    'china_taiwan_risk': 'China-Taiwan geopolitical risk', 'panasonic_energy': 'Panasonic Energy',
    'lg_energy_solution': 'LG Energy Solution', 'samsung_sdi': 'Samsung SDI', 'amazon_kuiper': 'Amazon Kuiper'
}

OFFICIAL_URLS = {
    'tesla': 'https://www.tesla.com/', 'spacex': 'https://www.spacex.com/', 'starlink': 'https://www.starlink.com/', 'xai': 'https://x.ai/',
    'neuralink': 'https://neuralink.com/', 'nvidia': 'https://www.nvidia.com/', 'tsmc': 'https://www.tsmc.com/', 'asml': 'https://www.asml.com/',
    'amd': 'https://www.amd.com/', 'broadcom': 'https://www.broadcom.com/', 'arm': 'https://www.arm.com/', 'micron': 'https://www.micron.com/',
    'sk_hynix': 'https://www.skhynix.com/', 'samsung_electronics': 'https://www.samsung.com/global/ir/', 'intel': 'https://www.intel.com/',
    'cadence': 'https://www.cadence.com/', 'synopsys': 'https://www.synopsys.com/', 'openai': 'https://openai.com/', 'anthropic': 'https://www.anthropic.com/',
    'google': 'https://abc.xyz/', 'meta': 'https://about.meta.com/', 'amazon': 'https://www.aboutamazon.com/', 'aws': 'https://aws.amazon.com/',
    'microsoft': 'https://www.microsoft.com/', 'oracle': 'https://www.oracle.com/', 'apple': 'https://www.apple.com/',
    'datacenters': 'https://www.iea.org/reports/energy-and-ai', 'cloud_market': 'https://www.srgresearch.com/articles/cloud-market-growth-stays-strong-in-q1-while-amazon-google-and-oracle-nudge-higher',
    'ai_agents': 'https://openai.com/index/new-tools-for-building-agents/', 'ai_inference_economics': 'https://www.anthropic.com/engineering',
    'us_china_chip_controls': 'https://www.bis.gov/press-release/commerce-strengthens-export-controls-advanced-computing-semiconductors-manufacturing-equipment',
    'china_taiwan_risk': 'https://www.csis.org/programs/china-power-project/taiwan', 'humanoid_robots': 'https://ifr.org/ifr-press-releases/news/humanoid-robots-moving-from-hype-to-industrial-application',
    'robotaxi_autonomy': 'https://waymo.com/', 'waymo': 'https://waymo.com/', 'zoox': 'https://zoox.com/', 'figure_ai': 'https://www.figure.ai/',
    'agility_robotics': 'https://agilityrobotics.com/', 'apptronik': 'https://apptronik.com/', 'unitree_robotics': 'https://www.unitree.com/',
    'boston_dynamics': 'https://bostondynamics.com/', 'fanuc': 'https://www.fanuc.co.jp/en/', 'abb_robotics': 'https://new.abb.com/products/robotics',
    'rockwell_automation': 'https://www.rockwellautomation.com/', 'siemens': 'https://www.siemens.com/', 'robot_actuators': 'https://www.harmonicdrive.net/',
    'robot_sensors': 'https://www.onsemi.com/applications/industrial/robotics', 'logistics_automation': 'https://www.mhi.org/fundamentals/automation',
    'industrial_automation': 'https://www.ifr.org/', 'ev_market': 'https://www.iea.org/reports/global-ev-outlook-2025', 'automotive_market': 'https://www.oica.net/category/production-statistics/',
    'byd': 'https://www.bydglobal.com/', 'toyota': 'https://global.toyota/', 'volkswagen': 'https://www.volkswagen-group.com/',
    'charging_infrastructure': 'https://afdc.energy.gov/fuels/electricity_infrastructure', 'battery_storage': 'https://www.iea.org/reports/batteries-and-secure-energy-transitions',
    'catl': 'https://www.catl.com/en/', 'panasonic_energy': 'https://www.panasonic.com/global/energy/', 'lg_energy_solution': 'https://www.lgensol.com/en',
    'samsung_sdi': 'https://www.samsungsdi.com/', 'albemarle': 'https://www.albemarle.com/', 'sqm': 'https://www.sqm.com/en/',
    'lithium': 'https://www.iea.org/reports/global-critical-minerals-outlook-2025', 'nickel': 'https://www.iea.org/reports/global-critical-minerals-outlook-2025',
    'graphite': 'https://www.iea.org/reports/global-critical-minerals-outlook-2025', 'cobalt': 'https://www.iea.org/reports/global-critical-minerals-outlook-2025',
    'rare_earths': 'https://www.iea.org/reports/global-critical-minerals-outlook-2025', 'energy': 'https://www.eia.gov/',
    'electricity_grid': 'https://www.energy.gov/gdo/grid-deployment-office', 'solar': 'https://www.iea.org/energy-system/renewables/solar-pv',
    'wind_power': 'https://www.iea.org/energy-system/renewables/wind', 'nuclear_power': 'https://www.world-nuclear.org/',
    'uranium': 'https://world-nuclear.org/information-library/nuclear-fuel-cycle/uranium-resources/uranium-and-depleted-uranium',
    'natural_gas': 'https://www.eia.gov/naturalgas/', 'oil': 'https://www.eia.gov/petroleum/', 'copper': 'https://www.iea.org/reports/global-critical-minerals-outlook-2025',
    'silver': 'https://www.silverinstitute.org/', 'aluminum': 'https://international-aluminium.org/', 'steel': 'https://worldsteel.org/',
    'transformers': 'https://www.energy.gov/gdo/articles/building-resilient-grid-transformers-and-transmission', 'space_launch_market': 'https://www.faa.gov/space',
    'satellite_internet': 'https://www.fcc.gov/space/satellite', 'amazon_kuiper': 'https://www.aboutamazon.com/what-we-do/devices-services/project-kuiper',
    'rocket_lab': 'https://www.rocketlabusa.com/', 'defense_space': 'https://www.spaceforce.mil/', 'telecom_market': 'https://www.itu.int/en/ITU-D/Statistics/',
    'digital_ads': 'https://www.iab.com/insights/internet-advertising-revenue-report/', 'ecommerce': 'https://www.census.gov/retail/ecommerce.html',
    'vr_ar_market': 'https://www.idc.com/promo/arvr', 'ai_consumer_devices': 'https://www.counterpointresearch.com/', 'elon_musk': 'https://www.tesla.com/elon-musk',
    'jensen_huang': 'https://www.nvidia.com/en-us/about-nvidia/management-team/', 'sam_altman': 'https://openai.com/about/', 'dario_amodei': 'https://www.anthropic.com/team',
    'mark_zuckerberg': 'https://about.meta.com/media-gallery/executives/mark-zuckerberg/', 'jeff_bezos': 'https://www.aboutamazon.com/about-us/leadership/jeff-bezos',
    'sundar_pichai': 'https://abc.xyz/investor/other/google-management-team/', 'lisa_su': 'https://www.amd.com/en/corporate/leadership/lisa-su.html'
}

IR_URLS = {
    'tesla': 'https://ir.tesla.com/', 'nvidia': 'https://investor.nvidia.com/', 'tsmc': 'https://investor.tsmc.com/english', 'asml': 'https://www.asml.com/en/investors',
    'amd': 'https://ir.amd.com/', 'broadcom': 'https://investors.broadcom.com/', 'arm': 'https://investors.arm.com/', 'micron': 'https://investors.micron.com/',
    'sk_hynix': 'https://www.skhynix.com/eng/ir/financialInfo.jsp', 'samsung_electronics': 'https://www.samsung.com/global/ir/', 'intel': 'https://www.intc.com/',
    'cadence': 'https://investor.cadence.com/', 'synopsys': 'https://investor.synopsys.com/', 'google': 'https://abc.xyz/investor/',
    'meta': 'https://investor.atmeta.com/', 'amazon': 'https://ir.aboutamazon.com/', 'microsoft': 'https://www.microsoft.com/en-us/Investor/',
    'oracle': 'https://investor.oracle.com/', 'apple': 'https://investor.apple.com/', 'byd': 'https://www.bydglobal.com/en/InvestorRelations.html',
    'toyota': 'https://global.toyota/en/ir/', 'volkswagen': 'https://www.volkswagen-group.com/en/investor-relations-15765', 'catl': 'https://www.catl.com/en/investor/',
    'panasonic_energy': 'https://holdings.panasonic/global/corporate/investors.html', 'lg_energy_solution': 'https://www.lgensol.com/en/investor-relations',
    'samsung_sdi': 'https://www.samsungsdi.com/ir/index.html', 'albemarle': 'https://investors.albemarle.com/', 'sqm': 'https://ir.sqm.com/English/default.aspx',
    'fanuc': 'https://www.fanuc.co.jp/en/ir/', 'abb_robotics': 'https://global.abb/group/en/investors', 'rockwell_automation': 'https://investors.rockwellautomation.com/',
    'siemens': 'https://www.siemens.com/global/en/company/investor-relations.html', 'rocket_lab': 'https://investors.rocketlabusa.com/'
}

SEGMENTS = {
    'tesla': ['Automotive; Energy generation and storage; Services and software.', 'Key KPIs: deliveries, automotive gross margin ex-credits, storage deployments, FSD/robotaxi evidence, capex.'],
    'spacex': ['Business lines: launch services, Starlink, government/defense missions, Starship development.', 'Key KPIs: launch cadence, Starship reusability progress, Starlink subscribers, capex intensity.'],
    'starlink': ['Business lines: residential broadband, enterprise, mobility, direct-to-cell, government services.', 'Key KPIs: subscribers, ARPU, capacity utilization, regulatory approvals.'],
    'xai': ['Business lines: frontier model development, consumer chatbot distribution, enterprise API/inference, training-cluster buildout.', 'Key KPIs: model releases, training compute scale, inference monetization, infrastructure partnerships.'],
    'nvidia': ['Reporting lens: Data Center, Gaming, Professional Visualization, Automotive and Robotics.', 'Key KPIs: data-center revenue mix, gross margin, networking attach rate, Blackwell/HBM supply, capex by hyperscalers.'],
    'tsmc': ['Reporting lens: wafer revenue by platform and by technology node; advanced packaging / CoWoS is strategically important.', 'Key KPIs: N3/N5 mix, CoWoS capacity, gross margin, capex, leading-edge customer concentration.'],
    'asml': ['Reporting lens: EUV, DUV, Installed Base Management, service/support.', 'Key KPIs: EUV system shipments, High-NA adoption, backlog, gross margin, China exposure.'],
    'amd': ['Reporting lens: Data Center, Client, Gaming, Embedded.', 'Key KPIs: MI300/MI350 ramp, EPYC share, gross margin, foundry capacity, cloud AI design wins.'],
    'broadcom': ['Reporting lens: semiconductor solutions and infrastructure software (including VMware).', 'Key KPIs: custom AI accelerator wins, networking demand, software renewal quality, operating margin.'],
    'arm': ['Reporting lens: royalty and license revenue tied to CPU/IP adoption across mobile, edge, and datacenter.', 'Key KPIs: royalty growth, v9 mix, datacenter CPU adoption, AI edge-device design wins.'],
    'micron': ['Reporting lens: DRAM, NAND, HBM/memory portfolio.', 'Key KPIs: HBM mix, bit demand, ASP cycle, capex discipline, inventory normalization.'],
    'sk_hynix': ['Reporting lens: DRAM, NAND, HBM leadership.', 'Key KPIs: HBM share, margins, capex, pricing cycle, Nvidia exposure.'],
    'samsung_electronics': ['Reporting lens: Device Solutions (memory/foundry), MX/mobile, consumer electronics, displays.', 'Key KPIs: HBM competitiveness, foundry recovery, handset margins, capex.'],
    'intel': ['Reporting lens: Client, Data Center/AI, Network/Edge, Foundry, Mobileye stake economics.', 'Key KPIs: foundry milestones, gross margin, capex, advanced packaging, AI accelerator traction.'],
    'cadence': ['Business lines: EDA software, IP, system analysis and verification.', 'Key KPIs: recurring software revenue, backlog, AI-assisted design adoption.'],
    'synopsys': ['Business lines: EDA, design IP, software integrity.', 'Key KPIs: software renewal, IP mix, semiconductor design activity.'],
    'google': ['Reporting lens: Search, YouTube ads, Network ads, Subscriptions/Platforms/Devices, Google Cloud, Other Bets.', 'Key KPIs: search monetization, Gemini distribution, cloud margin, TPU/data-center capex, Waymo rollout.'],
    'meta': ['Reporting lens: Family of Apps and Reality Labs.', 'Key KPIs: ad pricing, engagement, AI capex, Llama ecosystem pull, Reality Labs losses.'],
    'amazon': ['Reporting lens: North America, International, AWS.', 'Key KPIs: AWS growth/margin, retail operating leverage, logistics efficiency, capex, Kuiper spend.'],
    'aws': ['Business lines: compute, storage, database, AI/ML, custom silicon, marketplace/services.', 'Key KPIs: revenue growth, operating margin, AI workload mix, Trainium/Inferentia adoption.'],
    'microsoft': ['Reporting lens: Productivity and Business Processes, Intelligent Cloud, More Personal Computing.', 'Key KPIs: Azure AI growth, Copilot monetization, capex, OpenAI dependency.'],
    'oracle': ['Business lines: OCI/cloud infrastructure, database, applications.', 'Key KPIs: OCI growth, AI capacity wins, capex, remaining performance obligations.'],
    'apple': ['Reporting lens: iPhone, Mac, iPad, Wearables/Home/Accessories, Services.', 'Key KPIs: services margin, device refresh cycle, Apple Intelligence adoption, silicon roadmap.'],
    'waymo': ['Business lines: autonomous ride-hailing deployments, partnerships/licensing, fleet ops.', 'Key KPIs: paid rides, city launches, safety metrics, cost per ride.'],
    'byd': ['Reporting lens: autos, batteries, overseas expansion, commercial vehicles/energy exposure.', 'Key KPIs: unit share, export mix, battery integration, pricing power.'],
    'catl': ['Business lines: EV batteries, ESS batteries, services/recycling.', 'Key KPIs: cell shipments, LFP/sodium-ion mix, ESS growth, margins.'],
    'panasonic_energy': ['Business lines: cylindrical cells, 4680 development, automotive battery supply.', 'Key KPIs: 4680 yield, Tesla exposure, margin/capex balance.'],
    'lg_energy_solution': ['Business lines: EV batteries, ESS, advanced materials/services.', 'Key KPIs: customer mix, IRA exposure, ESS recovery, capex.'],
    'samsung_sdi': ['Business lines: EV batteries, ESS, electronic materials.', 'Key KPIs: premium battery mix, margins, customer diversification.'],
    'albemarle': ['Business lines: lithium and specialty materials.', 'Key KPIs: lithium realized pricing, volume growth, capex, project execution.'],
    'sqm': ['Business lines: lithium and specialty plant nutrients / iodine related businesses.', 'Key KPIs: lithium pricing, Chile resource policy, volume growth.'],
    'rocket_lab': ['Business lines: launch services, space systems, Neutron optionality.', 'Key KPIs: Electron cadence, backlog, space-systems mix, Neutron milestones.']
}

MARKET_MAPS = {
    'datacenters': ['Demand drivers: hyperscaler AI training and inference capex, enterprise GPU cloud demand, model-size growth.', 'Constraints: grid interconnection, transformers, power density, cooling, GPU/HBM availability.', 'Pricing mechanisms: colocation rents, cloud instance pricing, power cost, utilization rates.'],
    'cloud_market': ['Demand drivers: enterprise cloud migration, AI training/inference workloads, SaaS platform consumption.', 'Constraints: GPU supply, power, network capacity, customer optimization pressure.', 'Leading indicators: hyperscaler capex, cloud revenue growth, AI service attach rates.'],
    'ai_agents': ['Demand drivers: enterprise workflow automation, developer tools, lower-cost inference.', 'Constraints: model reliability, tool security, orchestration complexity, unit economics.'],
    'ai_inference_economics': ['Demand drivers: token growth, consumer usage, enterprise copilots, multimodal serving.', 'Constraints: GPU utilization, memory bandwidth, power cost, model compression quality.'],
    'humanoid_robots': ['Demand drivers: labor scarcity, warehouse/manufacturing automation, falling component costs.', 'Constraints: actuators, sensors, autonomy reliability, safety, total cost of ownership.'],
    'robotaxi_autonomy': ['Demand drivers: urban ride-hailing economics, autonomy software performance, regulatory rollout.', 'Constraints: safety approval, inference cost, fleet utilization, map/ops complexity.'],
    'ev_market': ['Demand drivers: battery cost declines, regulation, charging availability, model choice.', 'Constraints: affordability, charging reliability, subsidy roll-off, grid readiness.'],
    'automotive_market': ['Demand drivers: macro incomes, financing rates, replacement cycles, fleet demand.', 'Constraints: rates, commodity costs, regulation, consumer confidence.'],
    'battery_storage': ['Demand drivers: renewable intermittency, grid congestion, ancillary services, data-center power needs.', 'Constraints: cell supply, interconnection, project finance, inverter/transformer bottlenecks.'],
    'energy': ['Demand drivers: electrification, AI load growth, transport demand, industrial consumption.', 'Constraints: permitting, infrastructure, fuel supply, capital intensity.'],
    'electricity_grid': ['Demand drivers: electrification, data centers, EV charging, renewables interconnection.', 'Constraints: transformers, transmission build times, permitting, labor.'],
    'solar': ['Demand drivers: falling module costs, PPA demand, rooftop/utility economics.', 'Constraints: interconnection, interest rates, silver/copper inputs, land/permitting.'],
    'wind_power': ['Demand drivers: decarbonization mandates and utility-scale power demand.', 'Constraints: permitting, turbine economics, rare earth supply, transmission.'],
    'nuclear_power': ['Demand drivers: firm clean power demand, SMR interest, data-center baseload needs.', 'Constraints: permitting, capital cost, fuel cycle, construction lead time.'],
    'space_launch_market': ['Demand drivers: satellite deployments, defense launch, reusable launch economics.', 'Constraints: launch cadence, payload demand, regulatory approvals.'],
    'satellite_internet': ['Demand drivers: rural broadband, mobility, direct-to-cell, defense resilience.', 'Constraints: spectrum, satellite replenishment, terminal costs, capacity.'],
    'defense_space': ['Demand drivers: national-security launch, ISR constellations, resilient communications.', 'Constraints: budgets, procurement cycles, launch availability.'],
    'telecom_market': ['Demand drivers: data usage, broadband substitution, enterprise connectivity.', 'Constraints: spectrum, capex, pricing competition, regulation.'],
    'digital_ads': ['Demand drivers: user attention, performance attribution, AI targeting tools.', 'Constraints: privacy policy shifts, ad-load saturation, macro ad budgets.'],
    'ecommerce': ['Demand drivers: online penetration, delivery speed, marketplace selection.', 'Constraints: logistics cost, consumer demand, returns, competition.'],
    'vr_ar_market': ['Demand drivers: gaming, enterprise visualization, spatial computing ecosystems.', 'Constraints: hardware comfort, content, price, developer adoption.'],
    'ai_consumer_devices': ['Demand drivers: on-device AI use cases, smartphone refresh cycles, edge compute improvements.', 'Constraints: battery life, silicon cost, privacy, consumer willingness to pay.']
}

COMMODITY_MAPS = {
    'lithium': 'Pricing follows battery-grade carbonate/hydroxide supply-demand balance; leading indicators are EV/storage demand, brine/spodumene expansions, and Chinese converter margins.',
    'nickel': 'Pricing follows stainless and battery demand, Indonesia supply growth, and chemistry substitution toward LFP.',
    'graphite': 'Pricing and supply risk hinge on anode demand growth, synthetic-vs-natural mix, and China processing concentration.',
    'cobalt': 'Pricing is driven by battery cathode demand, DRC supply risk, and chemistry shifts away from cobalt intensity.',
    'rare_earths': 'Pricing and strategic risk depend on permanent-magnet demand, China processing dominance, and defense/clean-tech demand.',
    'uranium': 'Pricing reflects reactor restart/build demand, enrichment constraints, contracting cycles, and producer discipline.',
    'natural_gas': 'Pricing reflects storage, weather, LNG exports, power burn, and data-center-driven electricity demand.',
    'oil': 'Pricing reflects OPEC supply discipline, global transport demand, geopolitics, and substitution from EV adoption at the margin.',
    'copper': 'Pricing reflects grid/data-center/EV demand, mine supply growth, and smelter/refining constraints.',
    'silver': 'Pricing reflects PV and electronics industrial demand plus monetary/investment flows.',
    'aluminum': 'Pricing reflects power costs, lightweighting demand, and supply discipline in smelting.',
    'steel': 'Pricing reflects construction/manufacturing cycles, raw material costs, and infrastructure demand.'
}

PERSON_NOTES = {
    'elon_musk': 'Cross-company key person for Tesla, SpaceX, xAI, and Neuralink; monitor capital allocation, governance, and attention bandwidth.',
    'jensen_huang': 'Nvidia strategy setter; monitor product cadence, supply-chain coordination, and hyperscaler relationships.',
    'sam_altman': 'OpenAI strategy setter; monitor model roadmap, compute partnerships, governance, and monetization.',
    'dario_amodei': 'Anthropic strategy setter; monitor enterprise adoption, safety positioning, and capital intensity.',
    'mark_zuckerberg': 'Meta capital allocator for AI and Reality Labs; monitor ad monetization vs capex tolerance.',
    'jeff_bezos': 'Amazon/Kuiper strategic influence and long-horizon space optionality monitor.',
    'sundar_pichai': 'Google platform and AI execution leader; monitor Gemini integration, cloud AI, and capex priorities.',
    'lisa_su': 'AMD execution leader; monitor MI-series ramp, EPYC competitiveness, and foundry coordination.'
}

SECONDARY_URLS = {
    'spacex': 'https://www.faa.gov/space/stakeholder_engagement/spacex_starship', 'starlink': 'https://www.fcc.gov/document/fcc-authorizes-spacexs-starlink-satellite-broadband-service',
    'xai': 'https://x.ai/blog', 'neuralink': 'https://neuralink.com/blog/', 'openai': 'https://openai.com/news/', 'anthropic': 'https://www.anthropic.com/news',
    'datacenters': 'https://www.energy.gov/articles/energy-department-announces-initiatives-support-data-center-energy-demand',
    'battery_storage': 'https://www.nrel.gov/grid/energy-storage.html', 'ev_market': 'https://www.iea.org/reports/global-ev-outlook-2025',
    'electricity_grid': 'https://www.energy.gov/gdo/articles/building-better-grid-initiative'
}

QUALITY = {
    'investor_relations': '1.0', 'filings': '1.0', 'annual_report': '1.0', 'quarterly_report': '0.95', 'investor_presentation': '0.95',
    'earnings_transcript': '0.90', 'official_site': '0.85', 'research': '0.75', 'regulatory': '0.90', 'market_data': '0.80', 'leadership': '0.80'
}


def stable_hash(*parts: str) -> str:
    return hashlib.sha256('||'.join(parts).encode()).hexdigest()


def slug_title(slug: str) -> str:
    return DISPLAY_OVERRIDES.get(slug, slug.replace('_', ' ').replace('-', ' ').title())


def split_keywords(text: str) -> list[str]:
    return [part.strip() for part in text.split(';') if part.strip()]


def read_seed() -> list[dict[str, str]]:
    with SEED.open('r', encoding='utf-8', newline='') as handle:
        return [row for row in csv.DictReader(handle) if row.get('entity_id')]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text.strip() + '\n', encoding='utf-8')


def write_csv(path: Path, rows: list[dict[str, str]], header: list[str]) -> None:
    ensure_dir(path.parent)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, '') for key in header})


def sec_search_url(name: str) -> str:
    return f'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={quote(name)}&owner=exclude&count=40'


def source_priority(entity_type: str) -> list[str]:
    if entity_type in {'company', 'private_company'}:
        return ['investor relations' if entity_type == 'company' else 'official pages', 'filings' if entity_type == 'company' else 'company blog / newsroom', 'annual or quarterly materials' if entity_type == 'company' else 'credible interviews', 'investor presentations / product updates', 'earnings transcripts / conference talks', 'trade research']
    if entity_type in {'market', 'sector', 'infrastructure', 'technology'}:
        return ['authoritative research reports', 'regulators and standards bodies', 'official company materials', 'trade publications']
    if entity_type == 'commodity':
        return ['authoritative commodity / minerals outlooks', 'producer reports', 'market data', 'trade research']
    if entity_type == 'person':
        return ['official bio pages', 'earnings calls / letters', 'major interviews / conference appearances']
    if entity_type == 'regulation':
        return ['primary regulation / government releases', 'think-tank analysis', 'company risk disclosures']
    return ['official pages', 'research reports']


def relationship_type(src_type: str, dst_type: str) -> str:
    if dst_type == 'person':
        return 'person_affiliation'
    if dst_type == 'commodity':
        return 'cost_input'
    if dst_type in {'market', 'sector'}:
        return 'demand_driver'
    if dst_type == 'regulation':
        return 'regulatory_dependency'
    if dst_type in {'technology', 'infrastructure'}:
        return 'technology_dependency'
    if src_type in {'company', 'private_company'} and dst_type in {'company', 'private_company'}:
        return 'competitor'
    return 'macro_driver'


def forecast_metric(entity_type: str, name: str) -> tuple[str, str, str, str]:
    if entity_type in {'company', 'private_company'}:
        return ('revenue', 'USD bn', 'USD', 'Core business')
    if entity_type == 'commodity':
        return ('commodity price', 'index', 'USD', name)
    if entity_type == 'person':
        return ('market size', 'proxy index', 'USD', 'Linked ecosystem influence')
    return ('market size', 'USD bn', 'USD', name)


def source_bundle(slug: str, name: str, entity_type: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    official = OFFICIAL_URLS.get(slug, '')
    if official:
        out.append({'title': f'{name} official page', 'source_name': name.split('/')[0].strip(), 'source_type': 'official_site', 'url': official})
    if entity_type == 'company':
        ir = IR_URLS.get(slug, '')
        ticker = PUBLIC_TICKERS.get(slug, '')
        if ir:
            out.append({'title': f'{name} investor relations', 'source_name': name.split('/')[0].strip(), 'source_type': 'investor_relations', 'url': ir})
        filings = sec_search_url(name.split('/')[0].strip()) if slug not in {'tsmc', 'asml', 'byd', 'toyota', 'volkswagen', 'catl', 'panasonic_energy', 'lg_energy_solution', 'samsung_sdi', 'fanuc', 'abb_robotics', 'siemens', 'sk_hynix', 'samsung_electronics'} else (ir or official)
        transcript = f'https://seekingalpha.com/symbol/{ticker.split(".")[0]}/earnings/transcripts' if ticker and slug not in {'byd', 'toyota', 'volkswagen', 'catl', 'panasonic_energy', 'lg_energy_solution', 'samsung_sdi', 'fanuc', 'abb_robotics', 'siemens', 'sk_hynix', 'samsung_electronics'} else (ir or official)
        out.extend([
            {'title': f'{name} filings', 'source_name': 'SEC or company IR', 'source_type': 'filings', 'url': filings},
            {'title': f'{name} annual report / annual results', 'source_name': 'Company IR', 'source_type': 'annual_report', 'url': ir or official},
            {'title': f'{name} quarterly results', 'source_name': 'Company IR', 'source_type': 'quarterly_report', 'url': ir or official},
            {'title': f'{name} investor presentations', 'source_name': 'Company IR', 'source_type': 'investor_presentation', 'url': ir or official},
            {'title': f'{name} earnings transcript page', 'source_name': 'Seeking Alpha / company materials', 'source_type': 'earnings_transcript', 'url': transcript},
        ])
    elif entity_type == 'private_company':
        blog = SECONDARY_URLS.get(slug, '')
        if blog and blog != official:
            out.append({'title': f'{name} newsroom / research', 'source_name': name.split('/')[0].strip(), 'source_type': 'research', 'url': blog})
    elif entity_type in {'market', 'sector', 'infrastructure', 'technology', 'commodity', 'regulation'}:
        ref = SECONDARY_URLS.get(slug, '')
        if ref and ref != official:
            out.append({'title': f'{name} reference source', 'source_name': 'Authoritative research', 'source_type': 'research', 'url': ref})
    elif entity_type == 'person' and official:
        out.append({'title': f'{name} leadership / profile source', 'source_name': 'Official profile', 'source_type': 'leadership', 'url': official})
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for item in out:
        if not item['url'] or item['url'] in seen:
            continue
        seen.add(item['url'])
        deduped.append(item)
    return deduped[:6]


def sources_md(sources: list[dict[str, str]]) -> str:
    return '\n'.join(f'- <a href="{s["url"]}">{s["title"]}</a> ({s["source_type"].replace("_", " ")})' for s in sources)


def thesis_sections(entity_type: str, name: str, keywords: list[str]) -> dict[str, str]:
    monitor = ', '.join(keywords[:4])
    if entity_type in {'company', 'private_company'}:
        return {
            'bearish': '- Adoption, margins, or monetization lag while capex stays elevated.\n- Competitive or regulatory pressure weakens returns.',
            'base': '- Core business remains strategically relevant and linked adjacencies add optionality gradually.\n- Evidence improves incrementally rather than all at once.',
            'bullish': f'- Linked markets inflect in {name}\'s favor and operating leverage becomes visible.\n- Strategic optionality converts into durable revenue or margin upside.',
            'monitor': f'- Metrics to monitor: {monitor}.\n- Confirm with investor materials, filings, and product updates.'
        }
    if entity_type in {'market', 'sector', 'infrastructure', 'technology'}:
        return {
            'bearish': '- Demand underwhelms or bottlenecks persist longer than expected.\n- Capital spending slows before supply catches up.',
            'base': '- Structural demand grows but constraints and pricing cycles keep progress uneven.\n- Incumbents preserve share while new entrants pressure returns.',
            'bullish': '- Demand accelerates, bottlenecks loosen selectively, and pricing power stays supportive.\n- This node becomes more central to adjacent entity economics than consensus expects.',
            'monitor': f'- Metrics to monitor: {monitor}.\n- Track leading indicators, capex announcements, utilization, and regulatory milestones.'
        }
    if entity_type == 'commodity':
        return {
            'bearish': '- New supply or weaker demand pushes prices below incentive levels.\n- Downstream substitution reduces pricing power.',
            'base': '- Supply-demand stays cyclical but structurally supported by linked electrification and AI themes.',
            'bullish': '- Persistent bottlenecks tighten supply and lift prices / margins faster than demand models assume.',
            'monitor': f'- Metrics to monitor: {monitor}.\n- Track benchmark prices, project ramps, processing concentration, and substitution trends.'
        }
    if entity_type == 'person':
        return {
            'bearish': '- Governance, execution, or attention bandwidth degrades linked-entity performance.\n- Public narrative outruns operational proof.',
            'base': '- Leadership remains strategically important but effects stay mediated through linked companies and markets.',
            'bullish': '- Strategy, capital allocation, and product decisions create disproportionate upside across linked entities.',
            'monitor': f'- Metrics to monitor: {monitor}.\n- Track major strategic decisions, partnerships, and governance signals.'
        }
    return {
        'bearish': '- Adverse scenario pending source-backed refinement.',
        'base': '- Base scenario pending source-backed refinement.',
        'bullish': '- Bull scenario pending source-backed refinement.',
        'monitor': f'- Metrics to monitor: {monitor}.'
    }


def main() -> int:
    rows = read_seed()
    tracked_slugs = {row['entity_id'] for row in rows} | {'tesla'}
    manifest: list[dict[str, object]] = []
    for row in rows:
        manifest.append({
            'slug': row['entity_id'],
            'name': row['name'],
            'type': row['type'],
            'priority_label': row['priority'],
            'priority': PRIORITY_MAP.get(row['priority'], '3'),
            'status': STATUS_MAP.get(row['priority'], 'paused'),
            'keywords': split_keywords(row['keywords']),
            'connected': [part.strip() for part in row['connected_entities'].split(';') if part.strip()],
            'rationale': row['connection_rationale'].strip().rstrip('.'),
            'bootstrap_depth': row['bootstrap_depth'].strip(),
        })
    manifest.sort(key=lambda item: (0 if item['slug'] == 'tesla' else 1, int(item['priority']), str(item['name'])))
    name_by_slug = {str(item['slug']): str(item['name']) for item in manifest}

    for item in manifest:
        if item['type'] in {'company', 'private_company'}:
            item['keywords'].extend([f'{item["name"]} investor relations' if item['type'] == 'company' else f'{item["name"]} official site', f'{item["name"]} annual report' if item['type'] == 'company' else f'{item["name"]} product update'])
        elif item['type'] in {'market', 'sector', 'infrastructure', 'technology', 'commodity', 'regulation'}:
            item['keywords'].extend([str(item['name']), f'{item["name"]} report'])
        elif item['type'] == 'person':
            item['keywords'].extend([f'{item["name"]} interview', f'{item["name"]} strategy'])
        seen_kw: set[str] = set()
        deduped_kw: list[str] = []
        for keyword in item['keywords']:
            if keyword not in seen_kw:
                seen_kw.add(keyword)
                deduped_kw.append(keyword)
        item['keywords'] = deduped_kw[:8]
        item['connected'] = [slug for slug in item['connected'] if slug in tracked_slugs and slug != item['slug']]
        if item['slug'] == 'tesla':
            for extra in ['battery_storage', 'lithium', 'catl', 'byd', 'robotaxi_autonomy', 'humanoid_robots', 'solar', 'energy', 'nvidia', 'xai', 'elon_musk', 'charging_infrastructure', 'panasonic_energy', 'lg_energy_solution']:
                if extra in tracked_slugs and extra not in item['connected'] and extra != 'tesla':
                    item['connected'].append(extra)

    def connection_explanation(source_item: dict[str, object], target_slug: str) -> str:
        target_name = name_by_slug.get(target_slug, slug_title(target_slug))
        target_type = next((str(entry['type']) for entry in manifest if entry['slug'] == target_slug), 'other')
        source_name = str(source_item['name'])
        if target_type in {'market', 'sector'}:
            return f'{target_name} shapes {source_name} demand, pricing, market share, or capital allocation through adoption, competition, and cycle conditions.'
        if target_type == 'commodity':
            return f'{target_name} affects {source_name} cost, supply security, or pricing through critical material exposure and procurement risk.'
        if target_type == 'infrastructure':
            return f'{target_name} is a physical bottleneck or enabling network that influences {source_name} scaling, utilization, and returns.'
        if target_type == 'technology':
            return f'{target_name} drives {source_name} product capability, monetization, and valuation through software, compute, or platform dependence.'
        if target_type == 'regulation':
            return f'{target_name} changes {source_name} supply, market access, or capex decisions through policy and geopolitical constraints.'
        if target_type == 'person':
            return f'{target_name} influences {source_name} strategy, governance, narrative, capital allocation, and execution risk.'
        return f'{target_name} is a strategically relevant peer, supplier, customer, or dependency that changes {source_name} economics and optionality.'

    def overview_text(item: dict[str, object]) -> str:
        entity_type = str(item['type'])
        rationale = str(item['rationale'])
        name = str(item['name'])
        if entity_type in {'company', 'private_company'}:
            return f'{name} is tracked because {rationale}. Bootstrap content stays concise and source-backed so daily runs can replace placeholders with dated evidence.'
        if entity_type in {'market', 'sector', 'infrastructure', 'technology'}:
            return f'{name} is tracked as a system-level node because {rationale}. The bootstrap focuses on demand drivers, bottlenecks, pricing, and linked entities.'
        if entity_type == 'commodity':
            return f'{name} is tracked as a key input and pricing signal because {rationale}. The bootstrap emphasizes supply-demand, price transmission, and downstream exposure.'
        if entity_type == 'person':
            return f'{name} is tracked as a key-person and strategy connector because {rationale}.'
        if entity_type == 'regulation':
            return f'{name} is tracked because policy constraints can change supply, demand, valuation, and strategic behavior across the stack.'
        return rationale

    def business_lines_text(item: dict[str, object]) -> list[str]:
        slug = str(item['slug'])
        entity_type = str(item['type'])
        if slug in SEGMENTS:
            return SEGMENTS[slug]
        if entity_type in {'company', 'private_company'}:
            return [f'{item["name"]} should be tracked by its core products/services, strategic growth vectors, and capital intensity.', 'Bootstrap focus: revenue mix, margins, capex, customer concentration, and product roadmap evidence.']
        if entity_type in {'market', 'sector', 'infrastructure', 'technology'}:
            return MARKET_MAPS.get(slug, [f'{item["name"]} should be tracked through demand drivers, supply constraints, pricing, and leading indicators.'])
        if entity_type == 'commodity':
            return [COMMODITY_MAPS.get(slug, f'{item["name"]} should be tracked through supply-demand balance and price transmission.'), 'Bootstrap focus: price benchmark, supply additions, inventory / processing constraints, and downstream demand.']
        if entity_type == 'person':
            return [PERSON_NOTES.get(slug, f'{item["name"]} is tracked as a strategy and governance node.'), 'Bootstrap focus: strategic decisions, public guidance, and capital-allocation consequences across linked entities.']
        if entity_type == 'regulation':
            return [f'{item["name"]} should be tracked through policy text, enforcement, exemptions, and supply-chain spillovers.']
        return [str(item['rationale'])]

    entities_rows: list[dict[str, str]] = []
    relationship_rows: list[dict[str, str]] = []
    global_estimate_rows: list[dict[str, str]] = []
    global_source_rows: list[dict[str, str]] = []
    modified: list[Path] = []

    for item in manifest:
        slug = str(item['slug'])
        name = str(item['name'])
        entity_dir = ROOT / 'entities' / slug
        ensure_dir(entity_dir / 'wiki')
        ensure_dir(entity_dir / 'daily_reports')
        gitkeep = entity_dir / 'daily_reports' / '.gitkeep'
        if not gitkeep.exists():
            gitkeep.write_text('', encoding='utf-8')
            modified.append(gitkeep)

        sources = source_bundle(slug, name, str(item['type']))
        source_count = len(sources)
        display_connected = [(target_slug, name_by_slug.get(target_slug, slug_title(target_slug)), connection_explanation(item, target_slug)) for target_slug in item['connected']]
        connected_pipe = '|'.join(target_slug for target_slug, _, _ in display_connected)
        description = overview_text(item)
        sector = str(item['type']).replace('_', ' ').title()
        industry = str(item['rationale'])[:120]
        business_lines = ' | '.join(line.split(':', 1)[0] for line in business_lines_text(item)[:3])
        ticker = PUBLIC_TICKERS.get(slug, '')
        entities_rows.append({
            'entity_id': f'entity_{slug}', 'slug': slug, 'name': name, 'type': str(item['type']), 'status': str(item['status']), 'priority': str(item['priority']), 'ticker': ticker,
            'exchange': 'Public market' if ticker else 'Private / thematic', 'currency': 'USD', 'geography': 'Global', 'sector': sector, 'industry': industry,
            'business_lines': business_lines, 'description': description, 'search_keywords': '|'.join(item['keywords']), 'connected_entities': connected_pipe,
            'last_retrieval_at': NOW, 'last_report_date': TODAY, 'last_source_count': str(source_count), 'confidence': '0.60' if str(item['type']) in {'company', 'market', 'sector', 'infrastructure', 'technology', 'commodity'} else '0.55',
            'owner_notes': f'Bootstrap batch from seed CSV; depth {item["bootstrap_depth"]}; unresolved data should be tightened in daily runs.'
        })

        for target_slug, _, explanation in display_connected:
            target_type = next((str(entry['type']) for entry in manifest if entry['slug'] == target_slug), 'other')
            relationship_rows.append({
                'source_slug': slug, 'target_slug': target_slug, 'relationship_type': relationship_type(str(item['type']), target_type), 'direction': 'outbound',
                'importance': 'high' if str(item['priority']) == '1' else 'medium', 'mechanism': explanation, 'why_connected': explanation,
                'evidence_url': sources[0]['url'] if sources else OFFICIAL_URLS.get(slug, ''), 'last_reviewed_at': TODAY, 'confidence': '0.55'
            })

        metric, unit, currency, business_line = forecast_metric(str(item['type']), name)
        thesis = thesis_sections(str(item['type']), name, list(item['keywords']))
        estimate_row = {
            'entity_slug': slug, 'entity_name': name, 'type': str(item['type']), 'business_line': business_line, 'metric': metric, 'unit': unit, 'currency': currency,
            'actual_or_estimate': 'estimate', 'year': YEAR, 'base_value': '', 'bearish_forecast': 'TBD', 'normal_forecast': 'TBD', 'bullish_forecast': 'TBD',
            'bearish_thesis': thesis['bearish'].split('\n')[0].lstrip('- ').strip(), 'normal_thesis': thesis['base'].split('\n')[0].lstrip('- ').strip(), 'bullish_thesis': thesis['bullish'].split('\n')[0].lstrip('- ').strip(),
            'source_url': sources[0]['url'] if sources else '', 'source_date': TODAY, 'updated_at': TODAY, 'confidence': '0.30', 'notes': 'Bootstrap placeholder row; replace TBD values after source-backed extraction.'
        }
        global_estimate_rows.append(estimate_row)
        write_csv(entity_dir / 'estimates.csv', [estimate_row], ESTIMATES_HEADER)
        modified.append(entity_dir / 'estimates.csv')

        local_source_rows: list[dict[str, str]] = []
        for source in sources:
            source_id = stable_hash(slug, source['url'])[:16]
            row = {
                'source_id': source_id, 'entity_slug': slug, 'title': source['title'], 'source_name': source['source_name'], 'source_type': source['source_type'], 'url': source['url'], 'author': '',
                'published_at': '', 'retrieved_at': NOW, 'quality_score': QUALITY.get(source['source_type'], '0.75'), 'recency_score': '0.50', 'relevance_score': '0.85',
                'used_in_update': 'false', 'summary_path': '', 'hash': stable_hash(slug, source['url']), 'notes': 'Bootstrap source queue; verify dates and extract facts in later daily runs.'
            }
            local_source_rows.append(row)
            global_source_rows.append(row)
        write_csv(entity_dir / 'source_log.csv', local_source_rows, SOURCE_LOG_HEADER)
        modified.append(entity_dir / 'source_log.csv')

        connections_md = '\n'.join(f'- {label}: {why}' for _, label, why in display_connected) or '- None yet.'
        keywords_md = '\n'.join(f'- "{keyword}"' for keyword in item['keywords'])
        source_priority_md = '\n'.join(f'- {entry}' for entry in source_priority(str(item['type'])))
        summary_lines = '\n'.join(f'- {line}' for line in business_lines_text(item)[:3])
        source_links = sources_md(sources)
        monitor_lines = thesis['monitor']

        write_text(entity_dir / 'wiki' / 'index.md', f'''# {name}

## Overview

{description}

## Current thesis summary

{summary_lines}

## Search keywords

{keywords_md}

## Connected entities

{connections_md}

## Source map

Priority source families:

{source_priority_md}

### Bootstrap source list

{source_links}
''')
        modified.append(entity_dir / 'wiki' / 'index.md')

        write_text(entity_dir / 'wiki' / 'business.md', f'''# {name} Business

## Core model

{summary_lines}

## Revenue / value drivers

- Primary thesis link: {item['rationale']}.
- Connected-entity mechanisms:
{connections_md}

## What to update in daily runs

{monitor_lines}
''')
        modified.append(entity_dir / 'wiki' / 'business.md')

        market_lines = MARKET_MAPS.get(slug, business_lines_text(item))
        write_text(entity_dir / 'wiki' / 'market.md', f'''# {name} Market

## Market map

''' + '\n'.join(f'- {line}' for line in market_lines) + f'''

## Linked entities

{connections_md}

## Sources

{source_links}
''')
        modified.append(entity_dir / 'wiki' / 'market.md')

        financials_lines = SEGMENTS.get(slug, business_lines_text(item))
        first_source = source_links.splitlines()[0] if source_links else '- No sources yet.'
        write_text(entity_dir / 'wiki' / 'financials.md', f'''# {name} Financials

## Reporting structure / KPI lens

''' + '\n'.join(f'- {line}' for line in financials_lines) + f'''

## Forecast row status

- Global estimate row created for `{slug}` with TBD numeric values pending source-backed extraction.
- Primary source queue starts with: {first_source}
''')
        modified.append(entity_dir / 'wiki' / 'financials.md')

        write_text(entity_dir / 'wiki' / 'technology.md', f'''# {name} Technology

## Technical / system bottlenecks

''' + '\n'.join(f'- {line}' for line in business_lines_text(item)[-2:]) + f'''

## Dependency chain

{connections_md}
''')
        modified.append(entity_dir / 'wiki' / 'technology.md')

        write_text(entity_dir / 'wiki' / 'people.md', f'''# {name} People

## Key people / governance nodes

- Track leadership, capital allocation, strategic commentary, and partnership signaling relevant to {name}.
- Most relevant linked people or companies:
{connections_md}
''')
        modified.append(entity_dir / 'wiki' / 'people.md')

        write_text(entity_dir / 'wiki' / 'risks.md', f'''# {name} Risks

## Major risks

- Execution risk versus thesis expectations.
- Regulatory, commodity, supply-chain, or demand-cycle shifts through connected entities.
- Narrative expansion without matching source-backed evidence.

## Open questions

- Which source in the bootstrap queue most likely changes the thesis first?
- Which connected entity creates the largest second-order surprise risk?
''')
        modified.append(entity_dir / 'wiki' / 'risks.md')

        write_text(entity_dir / 'wiki' / 'sources.md', f'''# {name} Sources

## Bootstrap source list

{source_links}

## Notes

- Do not store full article text.
- Add short summaries, extracted facts, dates, and relevance notes during daily runs.
''')
        modified.append(entity_dir / 'wiki' / 'sources.md')

        write_text(entity_dir / 'thesis.md', f'''# {name} Thesis

## Bearish thesis

### Key assumptions

{thesis['bearish']}

### Revenue and EBITDA path

- Source-backed numeric extraction still pending; downside case assumes weaker operating leverage or weaker market conditions.

### Market size path

- Addressable demand grows slower or becomes less profitable than bullish narratives assume.

### Business-line contribution

- Core lines remain important but adjacencies contribute less than hoped.

### Catalysts

- Weak demand, pricing pressure, regulation, or execution misses.

### Disconfirming evidence

- Stronger margins, better product/market fit, or faster deployment than expected.

### Signposts to monitor

{thesis['monitor']}

## Normal thesis

### Key assumptions

{thesis['base']}

### Revenue and EBITDA path

- Base case assumes strategic relevance persists while monetization improves in steps rather than a straight line.

### Market size path

- Linked markets grow, but bottlenecks and competition keep the path uneven.

### Business-line contribution

- Core business stays dominant while optionality remains additive rather than fully proven.

### Catalysts

- Execution consistency, capex discipline, and evidence-backed product progress.

### Disconfirming evidence

- Faster-than-expected margin erosion or weaker adoption.

### Signposts to monitor

{thesis['monitor']}

## Bullish thesis

### Key assumptions

{thesis['bullish']}

### Revenue and EBITDA path

- Upside case assumes operating leverage and adjacent-market monetization become source-backed and durable.

### Market size path

- End-market growth and share capture both beat conservative assumptions.

### Business-line contribution

- Higher-value adjacencies contribute more to growth and margins than the market currently credits.

### Catalysts

- Major partnerships, product milestones, falling input costs, or better-than-expected deployment data.

### Disconfirming evidence

- Bottlenecks persist or narrative outpaces measurable economics.

### Signposts to monitor

{thesis['monitor']}
''')
        modified.append(entity_dir / 'thesis.md')

        write_text(entity_dir / 'financial_report.md', f'''# {name} Financial Report

## Entity summary

{description}

## Business lines

''' + '\n'.join(f'- {line}' for line in financials_lines) + f'''

## Latest financials

- This bootstrap avoids inventing current figures where direct extraction was not completed. Use the linked annual/quarterly materials to replace placeholders with dated numbers.
- Priority KPIs: {', '.join(list(item['keywords'])[:5])}.

## Forecast table

| Scenario | Revenue path | EBITDA / operating path | Market size path | Confidence |
|---|---|---|---|---|
| Bearish | Pressure on adoption, pricing, or mix | Lower leverage / higher capex burden | Slower or less profitable growth | Low |
| Base | Strategic relevance persists, measured execution | Gradual improvement | Moderate structural growth | Medium |
| Bullish | Strong monetization and cleaner scaling | Better leverage and returns | Large adjacent-market upside | Low |

## Valuation framing

- Track how much of the current narrative is already embedded versus what still needs evidence from source-backed execution.

## Market expectations

- The most important question is which linked market or bottleneck changes economics first.

## Possible mispricing

- Bottleneck relief or worsening could move this entity faster than consensus models update.
- Narrative-heavy optionality may be under- or over-capitalized depending on proof of deployment.

## Major risks

- Execution slippage.
- Input-cost / regulatory / infrastructure bottlenecks.
- Competitive intensity and capital discipline.

## Connected-entity implications

{connections_md}

## Open questions

- Which upcoming official filing or update most likely changes the thesis?
- Which connected entity creates the biggest unpriced risk or upside?

## Sources

{source_links}
''')
        modified.append(entity_dir / 'financial_report.md')

    entities_rows.sort(key=lambda row: (0 if row['slug'] == 'tesla' else 1, int(row['priority']), row['slug']))
    relationship_rows.sort(key=lambda row: (row['source_slug'], row['target_slug']))
    global_estimate_rows.sort(key=lambda row: (row['entity_slug'], row['metric']))
    global_source_rows.sort(key=lambda row: (row['entity_slug'], row['title']))

    write_csv(ROOT / 'data' / 'entities.csv', entities_rows, ENTITIES_HEADER)
    write_csv(ROOT / 'data' / 'relationships.csv', relationship_rows, RELATIONSHIPS_HEADER)
    write_csv(ROOT / 'data' / 'estimates.csv', global_estimate_rows, ESTIMATES_HEADER)
    write_csv(ROOT / 'data' / 'source_log.csv', global_source_rows, SOURCE_LOG_HEADER)
    modified.extend([ROOT / 'data' / 'entities.csv', ROOT / 'data' / 'relationships.csv', ROOT / 'data' / 'estimates.csv', ROOT / 'data' / 'source_log.csv'])

    blocks: list[str] = []
    for item in manifest:
        connection_lines = [f'  - {name_by_slug.get(target_slug, slug_title(target_slug))}: {connection_explanation(item, target_slug)}' for target_slug in item['connected']]
        block = [f'## {item["name"]}', '', f'- Slug: {item["slug"]}', f'- Type: {item["type"]}', f'- Status: {item["status"]}', f'- Priority: {item["priority"]}', '- Search keywords:']
        block.extend(f'  - "{keyword}"' for keyword in item['keywords'])
        block.append('- Source priority:')
        block.extend(f'  - {entry}' for entry in source_priority(str(item['type'])))
        block.append('- Connected entities:')
        block.extend(connection_lines or ['  - None yet.'])
        block.extend([f'- Last retrieval: {NOW}', f'- Last report: {TODAY}', f'- Notes: {item["rationale"]}. Bootstrap depth {item["bootstrap_depth"]}; refine with daily runs and source-backed numeric extraction.'])
        blocks.append('\n'.join(block))
    write_text(ROOT / 'index.md', '# WorldModel Entity Index\n\nThis file is the canonical registry of tracked entities, search keywords, and connected entities.\n\n' + '\n\n'.join(blocks))
    modified.append(ROOT / 'index.md')

    report_path = ROOT / 'reports' / f'report_{TODAY}.md'
    ensure_dir(report_path.parent)
    modified_set = sorted({path.resolve() for path in modified if path.exists()})
    repo_links = []
    for path in modified_set:
        rel = path.relative_to(ROOT)
        link = os.path.relpath(path, start=report_path.parent)
        repo_links.append(f'- [`{rel.as_posix()}`]({Path(link).as_posix()})')

    seen_urls: set[str] = set()
    external_links: list[str] = []
    for item in manifest:
        for source in source_bundle(str(item['slug']), str(item['name']), str(item['type']))[:3]:
            if source['url'] not in seen_urls:
                seen_urls.add(source['url'])
                external_links.append(f'- <a href="{source["url"]}">{source["title"]}</a>')

    write_text(report_path, f'''# WorldModel bootstrap report {TODAY}

## Scope

- Parsed `.worldmodel/entity_seed_batch.csv`.
- Bootstrapped the next batch of tracked entities from the seed list.
- Updated Tesla links to batteries, lithium, CATL, BYD, robotaxi, humanoid robots, solar, energy, Nvidia, xAI, Panasonic Energy, and LG Energy Solution where relevant.

## Entities bootstrapped / refreshed

- Total tracked entries written to `index.md`: {len(manifest)}
- New or refreshed entity directories under `entities/`: {len(manifest)}
- Relationship rows written: {len(relationship_rows)}
- Global source-log rows written: {len(global_source_rows)}

## Modified repository files

''' + '\n'.join(repo_links) + f'''

## External source queue

''' + '\n'.join(external_links[:150]) + f'''

## What this bootstrap includes

- Root `index.md` entries with search keywords, source priority, and connected-entity explanations.
- Entity wiki skeletons with overview, business, market, financial, technology, people, risks, and sources pages.
- `thesis.md` and `financial_report.md` for each entity with bullish/base/bearish framing.
- One local and one global estimate row per entity using the standard CSV template.
- Global and per-entity source logs with metadata only.

## Unresolved questions / missing data

- Many public-company numeric rows remain `TBD` until direct annual/quarterly extraction is automated or completed manually.
- Several seed references point to untracked helper entities (`semiconductors`, `github`, `gm`, `china_supply_chain`, `ai_healthcare`, `dell`, `supermicro`, `arista`, `hyundai`); these were not bootstrapped in this batch.
- Some official sites block this execution environment or require dynamic browsing, so source queues may point to landing pages rather than a direct latest filing document.

## Next suggested deterministic improvements

- Add a dedicated bootstrap script for seed CSV ingestion so future batches do not require one-off generation.
- Add direct extractor helpers for US SEC companyfacts / 10-K / 10-Q parsing, plus IR-page parsers for major non-US companies.
- Add tracked helper entities for omitted references like `semiconductors` and `china_supply_chain`.
''')

    print(f'bootstrapped {len(manifest)} entities, {len(relationship_rows)} relationships, {len(global_source_rows)} sources -> {report_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
