# Welfare-ton MRV MVP Technical Specification

**Status**: Draft for Implementation
**Created**: 2026-05-11
**Purpose**: Technical specification for minimum viable product

---

## I. Product Overview

### What is Welfare-ton MRV?

A verification platform that measures ecological restoration outcomes across multiple dimensions and creates economic value for verified welfare outcomes.

**Core Value Proposition**: "Carbon credits that actually deliver ecological welfare"

### The Welfare-ton Formula

```
W = C × E × A × B × V × P

Where:
- C = verified CO2 sequestration (tCO2e/year)
- E = employment factor (job density × job quality)
- A = community agency factor (FPIC score, 0 = no consent = zero welfare-tons)
- B = biodiversity co-benefit (0.8 to 1.5 multiplier)
- V = verification confidence (0 to 1)
- P = permanence factor (risk-adjusted durability, 0 to 1)
```

**Key Property**: Zero in any dimension kills the product. This prevents greenwashing.

---

## II. MVP Scope

### What's In (v0.1)

| Feature | Priority | Description |
|---------|----------|-------------|
| Carbon verification API | P0 | Accept project data, return carbon estimate |
| Welfare-ton calculator | P0 | Compute W score from 6 dimensions |
| Project registration | P0 | Create/read project records |
| Verification report PDF | P1 | Generate human-readable verification report |
| Basic dashboard | P1 | View project status and welfare-ton scores |

### What's Out (v0.1)

| Feature | Reason | Future Version |
|---------|--------|----------------|
| Satellite integration | Requires partnerships | v0.2 |
| Ground-truth calibration | Requires field work | v0.3 |
| Registry integration | Requires Verra/Gold Standard API access | v0.4 |
| Payment processing | Requires legal structure | v1.0 |
| Multi-tenant | Requires auth infrastructure | v1.0 |

---

## III. API Design

### Base URL

```
https://api.welfare-ton.io/v1
```

### Authentication

API key authentication via header.

### Endpoints

#### 1. Register Project

```
POST /projects
```

**Request Body:**
```json
{
  "name": "Mangrove Restoration Pilot - Indonesia",
  "location": {
    "country": "ID",
    "coordinates": [-8.65, 115.22],
    "area_hectares": 100
  },
  "ecosystem_type": "mangrove",
  "start_date": "2026-06-01",
  "methodology": "Verra VM0033",
  "metadata": {
    "project_developer": "Eden Reforestation",
    "community_partners": ["Village A", "Village B"]
  }
}
```

**Response:**
```json
{
  "project_id": "proj_abc123",
  "name": "Mangrove Restoration Pilot - Indonesia",
  "status": "registered",
  "created_at": "2026-05-11T12:00:00Z"
}
```

#### 2. Submit Carbon Data

```
POST /projects/{project_id}/carbon
```

**Request Body:**
```json
{
  "measurement_date": "2026-12-01",
  "method": "biomass_estimation",
  "data": {
    "trees_planted": 50000,
    "survival_rate": 0.85,
    "avg_height_m": 1.2,
    "biomass_per_hectare_t": 15.5
  },
  "source": "field_survey",
  "verifier": "local_partner_org"
}
```

**Response:**
```json
{
  "carbon_id": "car_xyz789",
  "project_id": "proj_abc123",
  "estimated_sequestration_tco2e": 425.5,
  "confidence_interval": [380.2, 470.8],
  "verification_status": "pending"
}
```

#### 3. Submit Employment Data

```
POST /projects/{project_id}/employment
```

**Request Body:**
```json
{
  "reporting_period": "2026-Q4",
  "workers": {
    "total_fte": 25,
    "local_hires": 23,
    "women_percentage": 0.45
  },
  "wages": {
    "avg_daily_wage_usd": 6.50,
    "local_minimum_wage_usd": 3.00,
    "wage_ratio": 2.17
  },
  "working_conditions": {
    "safety_equipment_provided": true,
    "working_hours_compliant": true,
    "grievance_mechanism": true
  }
}
```

**Response:**
```json
{
  "employment_id": "emp_def456",
  "project_id": "proj_abc123",
  "employment_factor": 0.87,
  "job_quality_score": 0.92
}
```

#### 4. Submit Community Agency Data

```
POST /projects/{project_id}/agency
```

**Request Body:**
```json
{
  "fPIC_score": 0.95,
  "land_tenure": {
    "type": "community_managed",
    "documentation": "verified"
  },
  "governance": {
    "local_committee": true,
    "women_participation": 0.40,
    "decision_making_power": "shared"
  },
  "benefit_sharing": {
    "agreement_type": "revenue_share",
    "community_percentage": 0.25,
    "documented": true
  }
}
```

**Response:**
```json
{
  "agency_id": "agn_ghi012",
  "project_id": "proj_abc123",
  "agency_factor": 0.95,
  "risk_flags": []
}
```

#### 5. Submit Biodiversity Data

```
POST /projects/{project_id}/biodiversity
```

**Request Body:**
```json
{
  "assessment_date": "2026-12-15",
  "method": "rapid_assessment",
  "species": {
    "native_species_planted": 5,
    "invasive_species_present": false,
    "endemic_species_count": 2
  },
  "habitat": {
    "connectivity_score": 0.75,
    "corridor_created": true,
    "buffer_zone_hectares": 20
  },
  "monitoring": {
    "baseline_survey": true,
    "follow_up_planned": "2027-06-01"
  }
}
```

**Response:**
```json
{
  "biodiversity_id": "bio_jkl345",
  "project_id": "proj_abc123",
  "biodiversity_factor": 1.15,
  "notes": "Multi-species planting with endemic species"
}
```

#### 6. Calculate Welfare-tons

```
GET /projects/{project_id}/welfare-tons
```

**Response:**
```json
{
  "project_id": "proj_abc123",
  "calculation_date": "2026-12-31",
  "welfare_tons": {
    "total": 387.2,
    "breakdown": {
      "carbon_tco2e": 425.5,
      "employment_factor": 0.87,
      "agency_factor": 0.95,
      "biodiversity_factor": 1.15,
      "verification_confidence": 0.85,
      "permanence_factor": 0.95
    }
  },
  "quality_tier": "premium",
  "comparison": {
    "standard_carbon_credit_tco2e": 425.5,
    "welfare_ton_multiplier": 0.91
  },
  "verification_status": "verified",
  "certificate_url": "https://api.welfare-ton.io/v1/certificates/proj_abc123/2026"
}
```

#### 7. Generate Verification Report

```
GET /projects/{project_id}/report
```

**Response:** PDF document with:
- Project overview
- Carbon sequestration analysis
- Employment impact assessment
- Community agency verification
- Biodiversity co-benefits
- Welfare-ton calculation
- Verification statement
- Appendices (methodology, data sources)

---

## IV. Data Models

### Project

```python
class Project:
    id: str
    name: str
    location: Location
    ecosystem_type: EcosystemType
    start_date: date
    methodology: str
    status: ProjectStatus  # registered, active, verified, suspended
    created_at: datetime
    updated_at: datetime
    metadata: dict
```

### Carbon Measurement

```python
class CarbonMeasurement:
    id: str
    project_id: str
    measurement_date: date
    method: CarbonMethod
    estimated_sequestration_tco2e: float
    confidence_interval: tuple[float, float]
    verification_status: VerificationStatus
    data: dict
    source: str
    verifier: str
```

### Welfare-ton Calculation

```python
class WelfareTonCalculation:
    id: str
    project_id: str
    calculation_date: date
    
    # Six dimensions
    carbon_tco2e: float
    employment_factor: float  # 0-1
    agency_factor: float  # 0-1 (0 = no consent = zero welfare-tons)
    biodiversity_factor: float  # 0.8-1.5
    verification_confidence: float  # 0-1
    permanence_factor: float  # 0-1
    
    # Computed
    welfare_tons: float  # C × E × A × B × V × P
    quality_tier: QualityTier  # standard, premium, exceptional
    
    # Metadata
    verification_status: VerificationStatus
    certificate_url: str
```

---

## V. Implementation Stack

### Backend

| Component | Technology | Rationale |
|-----------|------------|-----------|
| API Framework | FastAPI | Async, type-safe, auto-docs |
| Database | PostgreSQL + PostGIS | Spatial queries for location |
| ORM | SQLAlchemy | Mature, well-documented |
| Task Queue | Celery + Redis | Async report generation |
| Storage | S3-compatible | PDF reports, evidence files |
| Auth | API keys (v0.1) then OAuth2 (v1.0) | Simple start, scale later |

### Frontend (v0.2)

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Framework | Next.js | React, SSR, API routes |
| Maps | Mapbox GL | Project location visualization |
| Charts | Recharts | Welfare-ton breakdown |
| PDF Viewer | React-PDF | Verification reports |

### Infrastructure

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Hosting | Fly.io or Railway | Simple deploy, scale later |
| CI/CD | GitHub Actions | Automated testing, deploy |
| Monitoring | Sentry | Error tracking |
| Logging | Structured JSON | Searchable logs |

---

## VI. Development Phases

### Phase 1: Core API (Weeks 1-4)

| Week | Deliverable |
|------|-------------|
| 1 | Project registration, CRUD operations |
| 2 | Carbon data submission, estimation logic |
| 3 | Employment, agency, biodiversity endpoints |
| 4 | Welfare-ton calculation, verification report |

### Phase 2: Dashboard (Weeks 5-6)

| Week | Deliverable |
|------|-------------|
| 5 | Project list, detail views |
| 6 | Welfare-ton visualization, PDF download |

### Phase 3: Pilot (Weeks 7-12)

| Week | Deliverable |
|------|-------------|
| 7-8 | Onboard 1-2 pilot projects |
| 9-10 | Iterate based on feedback |
| 11-12 | Prepare for first verification cycle |

---

## VII. Pricing Model

### API Pricing (v0.1 - Pilot)

| Tier | Price | Features |
|------|-------|----------|
| Pilot | Free | Up to 5 projects, basic support |
| Standard | $0.10/ton verified | Unlimited projects, email support |
| Enterprise | $0.25/ton + $500/mo | Priority support, custom methodology |

### Revenue Projections

| Scenario | Year 1 | Year 2 | Year 3 |
|----------|--------|--------|--------|
| Conservative (100K tons) | $10K | $25K | $100K |
| Moderate (1M tons) | $100K | $250K | $1M |
| Optimistic (10M tons) | $1M | $2.5M | $10M |

---

## VIII. Success Metrics

### Technical Metrics

| Metric | Target (v0.1) | Target (v1.0) |
|--------|---------------|---------------|
| API uptime | 99% | 99.9% |
| Response time (p95) | less than 500ms | less than 200ms |
| Calculation accuracy | 95% | 99% |

### Business Metrics

| Metric | Target (6 months) | Target (12 months) |
|--------|-------------------|---------------------|
| Pilot projects | 2-3 | 5-10 |
| Tons verified | 10,000 | 100,000 |
| Revenue | $1,000 | $10,000 |
| Customer NPS | greater than 50 | greater than 70 |

---

## IX. Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Methodology disputes | Medium | High | Partner with standards bodies early |
| Data quality issues | High | Medium | Validation layer, confidence scoring |
| Regulatory changes | Medium | Medium | Design for flexibility, monitor ICVCM |
| Competition (Sylvera, Pachama) | High | Medium | Differentiate on multi-dimensional approach |
| Customer acquisition | High | High | Focus on pilot success, case studies |

---

## X. Next Steps

### Immediate (This Week)

1. Set up development environment
2. Create FastAPI project skeleton
3. Define database schema
4. Implement project registration endpoint

### Short-term (Next 2 Weeks)

1. Implement carbon estimation logic
2. Build welfare-ton calculator
3. Create basic test suite
4. Deploy to staging environment

### Medium-term (Next Month)

1. Complete all API endpoints
2. Build dashboard MVP
3. Onboard first pilot project
4. Iterate based on feedback

---

## XI. Dependencies

### Required for v0.1

- Development environment (Python 3.11+, PostgreSQL)
- API key generation system
- PDF generation library (WeasyPrint or ReportLab)

### Required for v0.2

- Frontend framework (Next.js)
- Mapbox API key
- S3-compatible storage

### Required for v1.0

- OAuth2 integration
- Registry API access (Verra, Gold Standard)
- Satellite data partnership

---

## XII. References

- Verra VM0033 Methodology: Tidal Wetland and Seagrass Restoration
- Gold Standard for Global Goals
- ICVCM Core Carbon Principles
- Plan Vivo Standard
- Welfare-ton formula: W = C × E × A × B × V × P (dharma_swarm foundations)

---

*Specification version: 0.1*
*Created: 2026-05-11*
*Status: Ready for implementation*