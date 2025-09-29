# File Management Service

File Management service handles all the tenant and file related operations. It includes functionality to create tenant, get tenant information, modify tenant configurations like maximum size allowed, file extentions etc, delete tenant.
For every tenant, the service contains complete file management service functions. User can upload a file, modify the metadata of the file, download files, delete files, get files list and user stats.

#### Features

**Tenant Features**:

- Creating Tenant
- Deleting Tenant (this will delete all the files associated with that tenant from the file storage)
- Modifying tenant configurations (eg. maximum file size, allowed extensions)
- Get tenant files and stats

**File Managment Features** (all operations are async - with caching support for repeated operations and user configurations)

- Upload File
- Download File
- Delete File
- List Files
- Update Metadata

### Rules for Storing Files

- Once a tenant is created, file storage creates a new folder associated with that tenant using tenant ID
- If the tenant is deleted, the folder associated with that tenant is also deleted permanently along with the files and folders in that
- Once a file is uploaded, it is stored in the date and month based folder for that particular user. This assists in efficient searching and sorting of documents. The file is stored in this format:

```bash
storage_base_path/
├── <tenant_code>/
│ └── YYYY-MM/
│ └── <file_name.ext>
```

- Deleting a file removes storage + DB metadata

---

## API Endpoints

#### Tenant Management

- `POST /api/tenants/` - Create tenant
- `GET /api/tenants/{tenant_code}` - Get tenant details
- `PUT /api/tenants/{tenant_code}` - Update tenant
- `DELETE /api/tenants/{tenant_code}` - Delete tenant
- `GET /api/tenants/{tenant_code}/stats` - Get tenant statistics

#### File Management

- `POST /api/files/upload` - Upload file
- `GET /api/files/{file_id}` - Get file metadata
- `GET /api/files/{file_id}/download` - Download file
- `DELETE /api/files/{file_id}` - Delete file
- `GET /api/files/tenant/{tenant_code}` - List files for tenant
- `POST /api/files/search` - Advanced file search
- `POST /api/files/bulk-delete` - Bulk delete files

---

## System Architecture

![image](https://github.com/SanvedN/file-system/blob/main/diagrams/tenant-sys.png?raw=true)
