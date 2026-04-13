from django.db import models
import uuid

class StoreLocation(models.Model):
    name = models.CharField(max_length=50,blank=False)
    shortname = models.CharField(max_length=12,blank=False)
    
    def __str__(self):
        return f"{self.name}"

class County(models.Model):
    name = models.CharField(max_length=50,blank=False)
    taxrate = models.FloatField(default=0.00)
    
    def __str__(self):
        return f"{self.name}"
    
class Referral(models.Model):
    name = models.CharField(max_length=50,blank=False)
    def __str__(self):
        return f"{self.name}"


class Customer(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=100)
    first_name2 = models.CharField(max_length=100,blank=True)
    last_name2 = models.CharField(max_length=100,blank=True)
    address = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    zip = models.CharField(max_length=15)
    # county fk
    county = models.ForeignKey(County,on_delete=models.CASCADE,null=True)
    emailoptout  = models.CharField(max_length=1,blank=True)
    cellphone = models.CharField(max_length=12,blank=True)
    cellphone2 = models.CharField(max_length=12,blank=True)
    home_phone = models.CharField(max_length=12,blank=True)
    work_phone = models.CharField(max_length=12,blank=True)
    work_phone2 = models.CharField(max_length=12,blank=True)
    status_flag = models.CharField(max_length=1,blank=True)
    # assignedto assigned_staff
    assigned_staff = models.CharField(max_length=100,blank=True)
    # custcode prefix for jobcodes, was 5chars
    # needs to be vetted against old jobs to prevent repeats
    cust_code = models.CharField(max_length=7,blank=True)     
    # referral fk
    referral = models.ForeignKey(Referral,on_delete=models.CASCADE,null=True)
    notes = models.CharField(max_length=300,blank=True)
    # track object creation and updates
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.CharField(max_length=100, blank=True)
    updated_by = models.CharField(max_length=100, blank=True)
    # track object deletion (soft delete)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.first_name}  {self.last_name}"
    
    @property
    def is_active(self):
        """Check if customer is active based on status_flag."""
        return self.status_flag == 'A' if self.status_flag else False
    
    @property
    def is_builder(self):
        """Check if customer is a builder based on status_flag or other logic."""
        # This might need to be adjusted based on your business logic
        # For now, checking if status_flag contains 'B' or if there's a builder flag
        return self.status_flag == 'B' if self.status_flag else False
    
    def save(self, *args, **kwargs):
        # Auto-generate cust_code if not provided
        if not self.cust_code:
            # Get customer name components
            last_name = self.last_name if self.last_name else ""
            first_name = self.first_name if self.first_name else ""
            
            # Get first 4 letters of last name (or all if shorter than 4)
            # Convert to lowercase first, then capitalize first letter
            if last_name:
                last_name_part = last_name[:4].lower().capitalize()
            else:
                last_name_part = ""
            
            # Get first 2 letters of first name (or less if shorter)
            # Convert to lowercase first, then capitalize first letter
            if first_name:
                if len(first_name) >= 2:
                    first_name_part = first_name[:2].lower().capitalize()
                else:
                    first_name_part = first_name.lower().capitalize()
            else:
                first_name_part = ""
            
            # Combine to create customer code
            self.cust_code = f"{last_name_part}{first_name_part}"
        
        super().save(*args, **kwargs)

