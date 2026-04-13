# Job Management App

The Job app provides comprehensive job management functionality for the AllenKit system, allowing users to create and manage jobs that link customers with sitework quotes and product quotes.

## Features

### Core Functionality
- **Job Creation**: Create jobs with customer information, descriptions, and budget tracking
- **Quote Integration**: Link jobs with sitework quotes and multiple product quotes
- **Status Management**: Track job status (Active, Inactive, Completed, Pending, On Hold)
- **Auto-numbering**: Automatic job number generation (format: JOB-YYYY-XXXX)
- **Cost Calculation**: Automatic calculation of total job costs from all associated quotes

### Models

#### Job
- Links customers with sitework quotes and product quotes
- Includes job description, status, timeline, and budget tracking
- Auto-generates job numbers
- Calculates total costs from all associated quotes

#### JobProductQuote
- Many-to-many relationship between jobs and product quotes
- Allows multiple product quotes per job
- Includes notes and timestamps for the relationship

### Views

#### Dashboard (`/job/`)
- Overview of job statistics
- Recent jobs list
- Quick action buttons
- Status distribution charts

#### Job List (`/job/list/`)
- Searchable and filterable job list
- Pagination support
- Status badges and action buttons

#### Job Detail (`/job/<id>/`)
- Complete job information display
- Customer details sidebar
- Associated quotes management
- Cost calculations

#### Job Forms (`/job/create/`, `/job/<id>/edit/`)
- Create and edit job information
- Form validation
- Date range validation

### Admin Interface

The job app includes a comprehensive admin interface with:
- Job management with inline product quote editing
- Search and filtering capabilities
- Optimized queries with select_related
- Export/import functionality

## Usage

### Creating a Job
1. Navigate to `/job/create/`
2. Select a customer
3. Add job description and details
4. Optionally link a sitework quote
5. Set budget and timeline
6. Save the job

### Adding Product Quotes to a Job
1. View job details at `/job/<id>/`
2. Click "Add Product Quote" button
3. Select from available active product quotes
4. Add optional notes
5. Save the relationship

### Managing Job Status
- Update job status through the edit form
- Status options: Active, Inactive, Completed, Pending, On Hold
- Status affects job visibility and calculations

## Integration

The job app integrates with:
- **CRM App**: Customer information and management
- **Sitework App**: Sitework quotes and calculations
- **Product App**: Product quotes and line items

## URL Patterns

- `/job/` - Dashboard
- `/job/list/` - Job list with search
- `/job/create/` - Create new job
- `/job/<id>/` - Job details
- `/job/<id>/edit/` - Edit job
- `/job/<id>/delete/` - Delete job
- `/job/<id>/add-product-quote/` - Add product quote to job
- `/job/<id>/remove-product-quote/<quote_id>/` - Remove product quote from job

## Testing

Run tests with:
```bash
python manage.py test job
```

Tests cover:
- Job creation and auto-numbering
- Product quote relationships
- Cost calculations
- Model string representations 