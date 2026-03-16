import { useState, useEffect } from "react";
import { useBranch } from "../context/BranchContext";

const fmt = (n) =>
  n == null ? "—" : n >= 1_000_000_000
    ? `${(n / 1_000_000_000).toFixed(1)}B`
    : n >= 1_000_000
    ? `${(n / 1_000_000).toFixed(1)}M`
    : n >= 1_000
    ? `${(n / 1_000).toFixed(0)}K`
    : String(Math.round(n));

const ISO3_TO_2 = {
  AFG:"AF",ALB:"AL",DZA:"DZ",AND:"AD",AGO:"AO",ARG:"AR",ARM:"AM",AUS:"AU",AUT:"AT",AZE:"AZ",
  BHS:"BS",BHR:"BH",BGD:"BD",BLR:"BY",BEL:"BE",BLZ:"BZ",BEN:"BJ",BTN:"BT",BOL:"BO",BIH:"BA",
  BWA:"BW",BRA:"BR",BRN:"BN",BGR:"BG",BFA:"BF",BDI:"BI",CPV:"CV",KHM:"KH",CMR:"CM",CAN:"CA",
  CAF:"CF",TCD:"TD",CHL:"CL",CHN:"CN",COL:"CO",COM:"KM",COD:"CD",COG:"CG",CRI:"CR",CIV:"CI",
  HRV:"HR",CUB:"CU",CYP:"CY",CZE:"CZ",DNK:"DK",DJI:"DJ",DOM:"DO",ECU:"EC",EGY:"EG",SLV:"SV",
  GNQ:"GQ",ERI:"ER",EST:"EE",SWZ:"SZ",ETH:"ET",FJI:"FJ",FIN:"FI",FRA:"FR",GAB:"GA",GMB:"GM",
  GEO:"GE",DEU:"DE",GHA:"GH",GRC:"GR",GTM:"GT",GIN:"GN",GNB:"GW",GUY:"GY",HTI:"HT",HND:"HN",
  HUN:"HU",ISL:"IS",IND:"IN",IDN:"ID",IRN:"IR",IRQ:"IQ",IRL:"IE",ISR:"IL",ITA:"IT",JAM:"JM",
  JPN:"JP",JOR:"JO",KAZ:"KZ",KEN:"KE",KWT:"KW",KGZ:"KG",LAO:"LA",LVA:"LV",LBN:"LB",LSO:"LS",
  LBR:"LR",LBY:"LY",LIE:"LI",LTU:"LT",LUX:"LU",MDG:"MG",MWI:"MW",MYS:"MY",MDV:"MV",MLI:"ML",
  MLT:"MT",MRT:"MR",MUS:"MU",MEX:"MX",MDA:"MD",MCO:"MC",MNG:"MN",MNE:"ME",MAR:"MA",MOZ:"MZ",
  MMR:"MM",NAM:"NA",NPL:"NP",NLD:"NL",NZL:"NZ",NIC:"NI",NER:"NE",NGA:"NG",MKD:"MK",NOR:"NO",
  OMN:"OM",PAK:"PK",PAN:"PA",PNG:"PG",PRY:"PY",PER:"PE",PHL:"PH",POL:"PL",PRT:"PT",QAT:"QA",
  ROU:"RO",RUS:"RU",RWA:"RW",SAU:"SA",SEN:"SN",SRB:"RS",SLE:"SL",SGP:"SG",SVK:"SK",SVN:"SI",
  SOM:"SO",ZAF:"ZA",ESP:"ES",LKA:"LK",SDN:"SD",SUR:"SR",SWE:"SE",CHE:"CH",SYR:"SY",TWN:"TW",
  TJK:"TJ",TZA:"TZ",THA:"TH",TLS:"TL",TGO:"TG",TTO:"TT",TUN:"TN",TUR:"TR",TKM:"TM",UGA:"UG",
  UKR:"UA",ARE:"AE",GBR:"GB",USA:"US",URY:"UY",UZB:"UZ",VEN:"VE",VNM:"VN",YEM:"YE",ZMB:"ZM",
  ZWE:"ZW",HKG:"HK",MAC:"MO",KOR:"KR",PRK:"KP",
};

const NAME_TO_2 = {
  "afghanistan":"AF","albania":"AL","algeria":"DZ","andorra":"AD","angola":"AO","argentina":"AR",
  "armenia":"AM","australia":"AU","austria":"AT","azerbaijan":"AZ","bahrain":"BH","bangladesh":"BD",
  "belarus":"BY","belgium":"BE","belize":"BZ","bhutan":"BT","bolivia":"BO","bosnia":"BA",
  "botswana":"BW","brazil":"BR","brunei":"BN","bulgaria":"BG","cambodia":"KH","cameroon":"CM",
  "canada":"CA","chile":"CL","china":"CN","colombia":"CO","croatia":"HR","cuba":"CU","cyprus":"CY",
  "czech republic":"CZ","czechia":"CZ","denmark":"DK","ecuador":"EC","egypt":"EG","estonia":"EE",
  "ethiopia":"ET","fiji":"FJ","finland":"FI","france":"FR","germany":"DE","ghana":"GH","greece":"GR",
  "guatemala":"GT","hong kong":"HK","hungary":"HU","iceland":"IS","india":"IN","indonesia":"ID",
  "iran":"IR","iraq":"IQ","ireland":"IE","israel":"IL","italy":"IT","jamaica":"JM","japan":"JP",
  "jordan":"JO","kazakhstan":"KZ","kenya":"KE","kuwait":"KW","laos":"LA","latvia":"LV","lebanon":"LB",
  "libya":"LY","liechtenstein":"LI","lithuania":"LT","luxembourg":"LU","macau":"MO","macao":"MO",
  "malaysia":"MY","maldives":"MV","mali":"ML","malta":"MT","mauritius":"MU","mexico":"MX",
  "moldova":"MD","monaco":"MC","mongolia":"MN","montenegro":"ME","morocco":"MA","mozambique":"MZ",
  "myanmar":"MM","nepal":"NP","netherlands":"NL","new zealand":"NZ","nicaragua":"NI","nigeria":"NG",
  "north korea":"KP","norway":"NO","oman":"OM","pakistan":"PK","panama":"PA","paraguay":"PY",
  "peru":"PE","philippines":"PH","poland":"PL","portugal":"PT","qatar":"QA","romania":"RO",
  "russia":"RU","saudi arabia":"SA","senegal":"SN","serbia":"RS","singapore":"SG","slovakia":"SK",
  "slovenia":"SI","somalia":"SO","south africa":"ZA","south korea":"KR","spain":"ES","sri lanka":"LK",
  "sweden":"SE","switzerland":"CH","syria":"SY","taiwan":"TW","tajikistan":"TJ","tanzania":"TZ",
  "thailand":"TH","turkey":"TR","turkmenistan":"TM","uganda":"UG","ukraine":"UA",
  "united arab emirates":"AE","united kingdom":"GB","united states":"US","united states of america":"US",
  "uruguay":"UY","uzbekistan":"UZ","venezuela":"VE","vietnam":"VN","viet nam":"VN","yemen":"YE",
  "zambia":"ZM","zimbabwe":"ZW","lithuania":"LT","burkina faso":"BF","burundi":"BI","cabo verde":"CV",
  "democratic republic of congo":"CD","republic of congo":"CG","dominican republic":"DO",
  "el salvador":"SV","equatorial guinea":"GQ","eritrea":"ER","eswatini":"SZ","guinea":"GN",
  "guinea-bissau":"GW","guyana":"GY","haiti":"HT","honduras":"HN","ivory coast":"CI",
  "cote d'ivoire":"CI","kyrgyzstan":"KG","lesotho":"LS","liberia":"LR","madagascar":"MG",
  "malawi":"MW","mauritania":"MR","namibia":"NA","niger":"NE","north macedonia":"MK","papua new guinea":"PG",
  "rwanda":"RW","sierra leone":"SL","sudan":"SD","suriname":"SR","timor-leste":"TL","togo":"TG",
  "trinidad and tobago":"TT","tunisia":"TN","tuvalu":"TV",
};

const FLAG = (code) => {
  if (!code) return "🌐";
  const c = code.trim().toUpperCase();
  // Try ISO-2 directly
  let iso2 = c.length === 2 ? c : null;
  // Try ISO-3
  if (!iso2 && c.length === 3) iso2 = ISO3_TO_2[c] || null;
  // Try full country name
  if (!iso2) iso2 = NAME_TO_2[code.trim().toLowerCase()] || null;
  if (!iso2) return "🌐";
  try {
    return [...iso2].map((ch) =>
      String.fromCodePoint(0x1f1e6 - 65 + ch.charCodeAt(0))
    ).join("");
  } catch {
    return "🌐";
  }
};

function KolBadge({ kol }) {
  const hasOrganic = kol.organic_bookings > 0;
  return (
    <div className="bg-green-50 border border-green-200 rounded p-2 text-xs">
      <div className="font-semibold text-green-800">{kol.kol_name}</div>
      <div className="text-green-600 mt-0.5 space-y-0.5">
        {kol.target_audience && <div>Audience: {kol.target_audience}</div>}
        {kol.language && <div>Language: {kol.language}</div>}
        {hasOrganic ? (
          <div>{kol.organic_bookings} bookings · {fmt(kol.organic_revenue_vnd)} VND</div>
        ) : (
          <div className="text-gray-400">No organic bookings yet</div>
        )}
        {kol.status && <div>Status: {kol.status}</div>}
        <div className="flex gap-2 mt-1">
          {kol.link_ig && (
            <a href={kol.link_ig} target="_blank" rel="noopener noreferrer"
               className="text-indigo-600 hover:underline">IG</a>
          )}
          {kol.link_tiktok && (
            <a href={kol.link_tiktok} target="_blank" rel="noopener noreferrer"
               className="text-indigo-600 hover:underline">TikTok</a>
          )}
          {kol.link_youtube && (
            <a href={kol.link_youtube} target="_blank" rel="noopener noreferrer"
               className="text-indigo-600 hover:underline">YT</a>
          )}
        </div>
      </div>
    </div>
  );
}

function AdsBadge({ ad }) {
  return (
    <div className="bg-blue-50 border border-blue-200 rounded p-2 text-xs">
      <div className="text-blue-800 space-y-0.5">
        {ad.target_country && <div className="font-semibold">{ad.target_country}</div>}
        {ad.target_audiences && <div>Audience: {ad.target_audiences}</div>}
        <div>Spend: {fmt(ad.total_cost_vnd)} VND</div>
        {ad.total_impressions > 0 && (
          <div>{fmt(ad.total_impressions)} impressions · {fmt(ad.total_clicks)} clicks</div>
        )}
        {ad.total_leads > 0 && <div>{ad.total_leads} leads</div>}
      </div>
    </div>
  );
}

function CoverageDetail({ item }) {
  const hasKol = !item.kol_gap;
  const hasAds = !item.ads_gap;
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">
      <div>
        <div className="text-xs font-semibold text-gray-500 uppercase mb-2">KOL Coverage</div>
        {hasKol ? (
          <div className="space-y-2">
            {item.kol_coverage.map((k) => <KolBadge key={k.kol_name} kol={k} />)}
          </div>
        ) : (
          <div className="bg-orange-50 border border-orange-200 rounded p-3 text-xs text-orange-700">
            <div className="font-semibold mb-1">Action needed</div>
            {item.action_items.filter((a) => a.includes("KOL")).map((a, i) => (
              <div key={i}>→ {a}</div>
            ))}
          </div>
        )}
      </div>
      <div>
        <div className="text-xs font-semibold text-gray-500 uppercase mb-2">Paid Ads Coverage</div>
        {hasAds ? (
          <div className="space-y-2">
            {item.ads_coverage.map((ad, i) => <AdsBadge key={i} ad={ad} />)}
          </div>
        ) : (
          <div className="bg-orange-50 border border-orange-200 rounded p-3 text-xs text-orange-700">
            <div className="font-semibold mb-1">Action needed</div>
            {item.action_items.filter((a) => a.includes("Ads")).map((a, i) => (
              <div key={i}>→ {a}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function VolumeRow({ item }) {
  const [expanded, setExpanded] = useState(false);
  const hasActions = item.action_items.length > 0;
  return (
    <>
      <tr
        className={`border-b hover:bg-gray-50 cursor-pointer ${hasActions ? "border-l-2 border-l-orange-400" : ""}`}
        onClick={() => setExpanded((v) => !v)}
      >
        <td className="px-3 py-2 text-xs text-gray-400 w-8">{item.rank}</td>
        <td className="px-3 py-2">
          <div className="flex items-center gap-2">
            <span className="text-base">{FLAG(item.country_code)}</span>
            <span className="text-sm font-medium text-gray-800">{item.country}</span>
          </div>
        </td>
        <td className="px-3 py-2 text-sm text-right font-mono text-gray-700">{item.booking_count}</td>
        <td className="px-3 py-2">
          {!item.kol_gap ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-100 text-green-700 text-xs font-medium">
              ✓ {item.kol_coverage.length} KOL{item.kol_coverage.length > 1 ? "s" : ""}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-100 text-red-600 text-xs font-medium">
              ✕ No KOL
            </span>
          )}
        </td>
        <td className="px-3 py-2">
          {!item.ads_gap ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 text-xs font-medium">
              ✓ Running
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-100 text-red-600 text-xs font-medium">
              ✕ No Ads
            </span>
          )}
        </td>
        <td className="px-3 py-2">
          {hasActions ? (
            <span className="text-orange-500 text-xs font-medium">
              {item.action_items.length} action{item.action_items.length > 1 ? "s" : ""}
            </span>
          ) : (
            <span className="text-green-500 text-xs">✓ Covered</span>
          )}
        </td>
        <td className="px-3 py-2 text-gray-400 text-xs">{expanded ? "▲" : "▼"}</td>
      </tr>
      {expanded && (
        <tr className="bg-gray-50 border-b">
          <td colSpan={7} className="px-6 py-3">
            <CoverageDetail item={item} />
          </td>
        </tr>
      )}
    </>
  );
}

function GrowthRow({ item }) {
  const [expanded, setExpanded] = useState(false);
  const hasActions = item.action_items.length > 0;
  return (
    <>
      <tr
        className={`border-b hover:bg-gray-50 cursor-pointer ${hasActions ? "border-l-2 border-l-orange-400" : ""}`}
        onClick={() => setExpanded((v) => !v)}
      >
        <td className="px-3 py-2 text-xs text-gray-400 w-8">{item.rank}</td>
        <td className="px-3 py-2">
          <div className="flex items-center gap-2">
            <span className="text-base">{FLAG(item.country_code)}</span>
            <span className="text-sm font-medium text-gray-800">{item.country}</span>
          </div>
        </td>
        <td className="px-3 py-2 text-sm text-right font-mono text-gray-700">{item.recent_bookings}</td>
        <td className="px-3 py-2 text-sm text-right text-gray-400">{item.prev_bookings}</td>
        <td className="px-3 py-2 text-right">
          {item.growth_pct != null ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-xs font-bold">
              ▲ {item.growth_pct}%
            </span>
          ) : (
            <span className="text-xs text-gray-400">New</span>
          )}
        </td>
        <td className="px-3 py-2">
          {!item.kol_gap ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-100 text-green-700 text-xs font-medium">
              ✓ {item.kol_coverage.length} KOL{item.kol_coverage.length > 1 ? "s" : ""}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-100 text-red-600 text-xs font-medium">
              ✕ No KOL
            </span>
          )}
        </td>
        <td className="px-3 py-2">
          {!item.ads_gap ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 text-xs font-medium">
              ✓ Running
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-100 text-red-600 text-xs font-medium">
              ✕ No Ads
            </span>
          )}
        </td>
        <td className="px-3 py-2 text-gray-400 text-xs">{expanded ? "▲" : "▼"}</td>
      </tr>
      {expanded && (
        <tr className="bg-gray-50 border-b">
          <td colSpan={8} className="px-6 py-3">
            <CoverageDetail item={item} />
          </td>
        </tr>
      )}
    </>
  );
}

function BranchSection({ branch }) {
  const [collapsed, setCollapsed] = useState(false);
  const allItems = [...(branch.top_volume || []), ...(branch.top_growth || [])];
  const kolGaps = allItems.filter((c) => c.kol_gap).length;
  const adsGaps = allItems.filter((c) => c.ads_gap).length;

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden mb-4">
      <div
        className="flex items-center justify-between px-5 py-3 bg-gray-50 border-b cursor-pointer"
        onClick={() => setCollapsed((v) => !v)}
      >
        <div className="flex items-center gap-3">
          <span className="font-semibold text-gray-800">{branch.branch_name}</span>
          <span className="text-xs text-gray-400">{branch.currency}</span>
        </div>
        <div className="flex items-center gap-3">
          {kolGaps > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-red-100 text-red-600 text-xs">{kolGaps} KOL gaps</span>
          )}
          {adsGaps > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-red-100 text-red-600 text-xs">{adsGaps} Ads gaps</span>
          )}
          {kolGaps === 0 && adsGaps === 0 && allItems.length > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-green-100 text-green-600 text-xs">Fully covered</span>
          )}
          <span className="text-gray-400 text-xs">{collapsed ? "▶" : "▼"}</span>
        </div>
      </div>

      {!collapsed && (
        <div className="divide-y divide-gray-100">

          {/* ── Top by Volume ── */}
          {branch.top_volume?.length > 0 && (
            <div>
              <div className="px-5 py-2 bg-indigo-50 border-b border-indigo-100">
                <span className="text-xs font-semibold text-indigo-700 uppercase tracking-wide">
                  Top 5 · Most Bookings (all-time)
                </span>
              </div>
              <table className="w-full">
                <thead>
                  <tr className="text-xs text-gray-500 bg-gray-50 border-b">
                    <th className="px-3 py-2 text-left w-8">#</th>
                    <th className="px-3 py-2 text-left">Country</th>
                    <th className="px-3 py-2 text-right">Bookings</th>
                    <th className="px-3 py-2 text-left">KOL</th>
                    <th className="px-3 py-2 text-left">Paid Ads</th>
                    <th className="px-3 py-2 text-left">Actions</th>
                    <th className="px-3 py-2 w-6"></th>
                  </tr>
                </thead>
                <tbody>
                  {branch.top_volume.map((c) => (
                    <VolumeRow key={c.country} item={c} />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* ── Top by Growth ── */}
          <div>
            <div className="px-5 py-2 bg-emerald-50 border-b border-emerald-100">
              <span className="text-xs font-semibold text-emerald-700 uppercase tracking-wide">
                Top 5 · Fastest Growing (last 90 days vs prior 90 days)
              </span>
            </div>
            {branch.top_growth?.length > 0 ? (
              <table className="w-full">
                <thead>
                  <tr className="text-xs text-gray-500 bg-gray-50 border-b">
                    <th className="px-3 py-2 text-left w-8">#</th>
                    <th className="px-3 py-2 text-left">Country</th>
                    <th className="px-3 py-2 text-right">Recent (90d)</th>
                    <th className="px-3 py-2 text-right">Prior (90d)</th>
                    <th className="px-3 py-2 text-right">Growth</th>
                    <th className="px-3 py-2 text-left">KOL</th>
                    <th className="px-3 py-2 text-left">Paid Ads</th>
                    <th className="px-3 py-2 w-6"></th>
                  </tr>
                </thead>
                <tbody>
                  {branch.top_growth.map((c) => (
                    <GrowthRow key={c.country} item={c} />
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="px-5 py-3 text-xs text-gray-400">
                No clear growth trends in the last 90 days.
              </div>
            )}
          </div>

        </div>
      )}
    </div>
  );
}

export default function CountryIntel() {
  const { selected, isAll } = useBranch();
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (!isAll) params.set("branch_id", selected);
    fetch(`/api/insights/country-intel?${params}`)
      .then((r) => r.json())
      .then((j) => {
        if (j.success) setData(j.data);
        else setError(j.error || "Failed to load");
      })
      .catch(() => setError("Network error"))
      .finally(() => setLoading(false));
  }, [selected, isAll]);

  const allItems = data.flatMap((b) => [
    ...(b.top_volume || []),
    ...(b.top_growth || []),
  ]);
  const totalKolGaps = allItems.filter((c) => c.kol_gap).length;
  const totalAdsGaps = allItems.filter((c) => c.ads_gap).length;
  const totalActions = allItems.reduce((s, c) => s + c.action_items.length, 0);
  const fullyCovered = allItems.filter((c) => !c.kol_gap && !c.ads_gap).length;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Country Intelligence</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Top guest countries × KOL coverage × Paid Ads coverage
        </p>
      </div>

      {!loading && data.length > 0 && (
        <div className="grid grid-cols-4 gap-3">
          <div className="bg-white rounded-lg border p-4">
            <div className="text-2xl font-bold text-green-600">{fullyCovered}</div>
            <div className="text-xs text-gray-500 mt-1">Fully Covered</div>
          </div>
          <div className="bg-white rounded-lg border p-4">
            <div className="text-2xl font-bold text-red-500">{totalKolGaps}</div>
            <div className="text-xs text-gray-500 mt-1">KOL Gaps</div>
          </div>
          <div className="bg-white rounded-lg border p-4">
            <div className="text-2xl font-bold text-red-500">{totalAdsGaps}</div>
            <div className="text-xs text-gray-500 mt-1">Ads Gaps</div>
          </div>
          <div className="bg-white rounded-lg border p-4">
            <div className={`text-2xl font-bold ${totalActions > 0 ? "text-orange-500" : "text-gray-400"}`}>
              {totalActions}
            </div>
            <div className="text-xs text-gray-500 mt-1">Actions Needed</div>
          </div>
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center h-40 text-gray-400 text-sm">Loading…</div>
      )}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-4 text-red-600 text-sm">{error}</div>
      )}
      {!loading && !error && data.length === 0 && (
        <div className="text-center py-16 text-gray-400">No reservation data found.</div>
      )}
      {!loading && !error && data.map((branch) => (
        <BranchSection key={branch.branch_id} branch={branch} />
      ))}
    </div>
  );
}
