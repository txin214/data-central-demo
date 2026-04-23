# sitework/models.py
from django.db import models
from django.db.models import Prefetch
from datetime import datetime
from django.utils import timezone
from django.contrib.auth.models import User
from crm.models import Customer


# sitework markets for labor calcs
class Market(models.Model):
    name = models.CharField(max_length=50,blank=False)
    mcode = models.CharField(max_length=10,blank=False)
    status = models.CharField(max_length=1,blank=True)
    
    def __str__(self):
        return f"{self.name}"         

# top tier category of sitework
class SiteworkCat(models.Model):
    # id
    name = models.CharField(max_length=50,blank=False)
    setupfee = models.FloatField(blank=False,default=0)
    orderby = models.IntegerField(blank=False,default=0)
    precedence = models.IntegerField(blank=False,default=0)
    percentcomplete = models.FloatField(blank=False,default=0)

    def __str__(self):
        return f"{self.name}"


# percent increase for each SiteworkCat for each Market
class MarketCategory(models.Model):
    market = models.ForeignKey(Market,on_delete=models.CASCADE,null=True,related_name='mcmarkets')
    siteworkcat = models.ForeignKey(SiteworkCat,on_delete=models.CASCADE,null=True,related_name='mc_cats')
    percentage = models.IntegerField(blank=True,null=True)

    def __str__(self):
        return f"{self.market} {self.siteworkcat} {self.percentage}"         



# categories of sitework tasks with details
class SiteworkSubCat(models.Model):
    # id
    workdesc = models.CharField(max_length=250,blank=False,default="")
    siteworkcat = models.ForeignKey(SiteworkCat,on_delete=models.CASCADE,null=True,related_name='ssc_cats')
    quantitydesc = models.CharField(max_length=10,blank=False,default="")
    basecost = models.FloatField(blank=False,default=0)
    unitamount = models.FloatField(blank=False,default=0)
    orderby = models.IntegerField(blank=False,default=0)
    drywall = models.IntegerField(blank=False,default=0)
    allowance = models.FloatField(blank=False,default=0)
    material = models.FloatField(blank=False,default=0)
    labor = models.FloatField(blank=False,default=0)
    profit = models.FloatField(blank=False,default=0)
    subfee = models.FloatField(blank=False,default=0)
    status = models.CharField(max_length=1,blank=True)
    kbflag = models.CharField(max_length=1,blank=True)
    group = models.IntegerField(blank=False,default=0)
    editallowance = models.CharField(max_length=1,blank=True)
    calckey = models.IntegerField(blank=False,default=0,unique=True)
    lastmodifieddate = models.DateTimeField(null=False, blank=False,default=timezone.now)
        
    def __str__(self):
        return f"{self.workdesc}"    

# These are the titles/subheadings shown in the sitework editor screens
class SiteworkSubCatGroup(models.Model):
    # id
    desc = models.CharField(max_length=80,blank=False,default="desc")
    group = models.IntegerField(blank=False,default=0)

    def __str__(self):
        return f"{self.desc}"    


class SiteworkQuote(models.Model):
    # id
    KBFLAG_CHOICES = [
        ('K', 'Kitchen'),
        ('B', 'Bath'),
        ('Both', 'Both'),
    ]
    
    customer = models.ForeignKey(Customer,on_delete=models.CASCADE,null=True,related_name='sq_customers')
    market = models.ForeignKey(Market,on_delete=models.CASCADE,null=True,related_name='sq_markets')
    quotedby = models.ForeignKey(User, on_delete=models.CASCADE,null=True,blank=True,related_name="+")    
    # job relationship (many SiteworkQuotes can belong to one Job)
    job = models.ForeignKey('job.Job', on_delete=models.CASCADE, null=True, blank=True, related_name='sitework_quotes')
    quotedate = models.DateField(blank=True, default=datetime.now)
    quotedesc = models.CharField(max_length=250, blank=True, null=True)
    status = models.CharField(max_length=1,blank=True, default='A')
    kbflag = models.CharField(max_length=10, choices=KBFLAG_CHOICES, blank=True, default='BOTH',null=True)
    overheadpercent = models.FloatField(blank=True, null=True)
    is_primary = models.BooleanField(default=False, help_text="Primary sitework quote for this job")

    def __str__(self):
        return f"{self.quotedesc or 'Sitework Quote'}"
    
    def subcreate(self, *args, **kwargs):
        #now create the sitework items
        if not self.pk:
            self.save()

        cats = SiteworkCat.objects.order_by('orderby')
        for c in cats:
            subcats = SiteworkSubCat.objects.filter(siteworkcat=c, status="A").order_by('orderby')
            for s in subcats:
                #print ("quote create sitework item: ",c.id," ",s.id)
                SiteworkQuoteLine.objects.add_lineitem(s.calckey, self.id)
    
    
    
    def save(self, *args, **kwargs):
        """Auto-set quotedby from job.soldby on creation only (allows manual override on updates)."""
        if self.pk is None and self.job and self.job.soldby and not self.quotedby:
            self.quotedby = self.job.soldby
        super().save(*args, **kwargs)
    
    @property
    def quoted_by_user(self):
        """Return the quotedby user, or job's soldby if quotedby is not set."""
        if self.quotedby:
            return self.quotedby
        if self.job and self.job.soldby:
            return self.job.soldby
        return None   


class QuoteLineManager(models.Manager):

    def update_qty(self, qty, subid, quoteid,):
        print("UPDATE_QTY:")
        #stuff = SiteworkQuoteLine.objects.get(id=subid)
        qute = SiteworkQuote.objects.get(id=quoteid)
        print("qute=",qute,"pk=",qute.pk)
        print("UPDATE_QTY2:")
        print("subid:",subid,"subcat=", SiteworkQuoteLine.objects.filter(pk=subid).first())
        obj = SiteworkQuoteLine.objects.get(pk=subid)
        obj.quantity = qty
        obj.save()
        print("debug: updated which=", subid, ",", quoteid, ", qty=", qty)
        return obj

    def update_comment(self, comment, subid, quoteid,):
        #stuff = SiteworkSubCat.objects.get(id=subid)
        qute = SiteworkQuote.objects.get(id=quoteid)
        # Only update existing rows; do not create with an explicit primary key
        obj = self.get(id=subid)
        if obj.quote_id != qute.id:
            print("WARNING: Quote mismatch on update_comment; line belongs to different quote")
            return obj
        obj.itemcomment = comment
        obj.save()
        return obj


    # this will create a QuoteLine item. 
    # typically only happens when a new quote is created
    # changed to not store the subcat primary key in the quote line.
    def add_lineitem(self, subid, quoteid,):
        stuff = SiteworkSubCat.objects.get(id=subid)
        qute = SiteworkQuote.objects.get(id=quoteid)
        create_defaults = {
            "quantity": 0,
            "itemcomment": "",
            "price": 0,
            "cat": stuff.siteworkcat,
            "workdesc": stuff.workdesc,
            "quantitydesc": stuff.quantitydesc,
            "basecost": stuff.basecost,
            "unitamount": stuff.unitamount,
            "orderby": stuff.orderby,
            "drywall": stuff.drywall,
            "allowance": stuff.allowance,
            "material": stuff.material,
            "labor": stuff.labor,
            "profit": stuff.profit,
            "subfee": stuff.subfee,
            "status": stuff.status,
            "kbflag": stuff.kbflag,
            "group": stuff.group,
            "editallowance": stuff.editallowance,
            "calckey": stuff.calckey,
            "subcatkey": stuff.calckey,
        }
        obj, created = self.get_or_create(
            quote=qute,
            #subcat=stuff,
            subcatkey=stuff.calckey,
            defaults=create_defaults,
        )
        #print("debug: create_flag= ", created, "calckey= ", obj.calckey, "group= ", obj.group)
        return obj

    def calc_price(self,quoteid):
        # Future work from old notes:
        # Old DC uses dollars but if we used minutes, we could use a labor rate to update prices easier.
        # Labor = CarpenterLab
        # Material = base cost + qty * per-unit cost
        # Unit Amount = (Allowance + Material + CarpenterLabor + Subfee) /Profit
        
        my_verbose = 1
        # 1. Create an array of qty values, all 0. (It will be a dictionary not an array)
        qtyvals = {}
        if my_verbose>0: print("calcprice-----------------------")
        # 2. copy qty from quote of any nonzero qty lines in the quotelines.
        # Make an expression out of all the current quantities
        # My first pythonic comprehension
        qtyvals = {item.calckey: item.quantity for item in SiteworkQuoteLine.objects.filter(quote=quoteid) }
        if my_verbose>0: print("qtyvals count=", len(SiteworkQuoteLine.objects.filter(quote=quoteid)) )

        # 3. now loop thru the array, like the ASP big switch statement
        # Result of this is some of the zero qty lines will become non-zero.
        for cid,qty in qtyvals.items():
            if cid == 85:
                # DEBRIS 
                if my_verbose>0: print("Debris qtyvals[85]=",qtyvals[85])
                debris=0
                debris += qtyvals[3]+qtyvals[4]+qtyvals[5]+qtyvals[6]+qtyvals[7]
                debris += qtyvals[10]+qtyvals[12]+qtyvals[13]+qtyvals[14]+qtyvals[15]
                debris += qtyvals[16]+qtyvals[17]+qtyvals[66]+qtyvals[67]+qtyvals[68]
                debris += qtyvals[69]+qtyvals[70]+qtyvals[72]+qtyvals[73]+qtyvals[74]
                debris += qtyvals[79]+qtyvals[80]+qtyvals[85]
                #  skipped 18,71 obsolete?
                if debris > 0:
                    if my_verbose>0: print("Debris UPDATE",debris,"qtyvals[85]=",qtyvals[85])
                    qtyvals[85] = 1

            elif cid == 157:
                # skylight domes
                if my_verbose>0: print("Skylight")
                qtyvals[157] = qtyvals[107]

            elif cid == 122:
                # install new window and caulk exterior
                if my_verbose>0: print("new window")
                qtyvals[122] = qtyvals[159]+qtyvals[278]
                # skipped 277

            elif cid == 124:
                # install tub and shower drain
                if my_verbose>0: print("tub shower drain")
                qtyvals[124] = qtyvals[73]

            elif cid == 127:
                if my_verbose>0: print("replace existing tub shower faucet")
                qtyvals[127] = qtyvals[124]+qtyvals[125]+qtyvals[126]

            elif cid == 136:
                if my_verbose>0: print("connect to existing plumbing vent")
                qtyvals[127] = qtyvals[124]+qtyvals[125]+qtyvals[126]

            elif cid == 140:
                if my_verbose>0: print("install new exhaust fan and duct to ext")
                qtyvals[136] = qtyvals[178]

            elif cid == 144:
                if my_verbose>0: print("connect sink and faucet")
                if qtyvals[3] > 0:
                    qtyvals[144] = 1

            elif cid == 294:
                if my_verbose>0: print("install ranch oak base trim")
                qtyvals[294] = qtyvals[69]

            elif cid == 211:
                if my_verbose>0: print("install new exhast fan and connect")
                qtyvals[211] = qtyvals[68]

            elif cid == 223:
                if my_verbose>0: print("drywall repairs from plumbing")
                if qtyvals[131] > 0:
                    qtyvals[223] = 10+ (qtyvals[131]* 5)

            elif cid == 220:
                if my_verbose>0: print("prime repairs only")
                qtyvals[220] = (qtyvals[222]*5)+qtyvals[352+qtyvals[223]+qtyvals[218]+qtyvals[224]]

            elif cid == 236:
                if my_verbose>0: print("install gold metal trim at doorway")
                if qtyvals[233]+qtyvals[231] > 0:
                    qtyvals[236] = 3

#            elif cid == 243:
                #print("install corian thresholds at doors")
                #if qtyvals[242] > 0:
                    #qtyvals[243] = 3
                # 242 skipped

            elif cid == 289:
                if my_verbose>0: print("set and connect toilet")
                if qtyvals[66] > 0:
                    qtyvals[289] = 1

            elif cid == 339:
                if my_verbose>0: print("floor: install ceramic tile and grout")
                if qtyvals[231] > 0:
                    qtyvals[339] = 0
                else:
                    qtyvals[339] = qtyvals[70]

            elif cid == 252:
                if my_verbose>0: print("top install priced in product")
                qtyvals[252] = qtyvals[5]

            elif cid == 338:
                if my_verbose>0: print("floor install 1/2 concrete board")
                temp=qtyvals[70]
                #if qtyvals[229]+qtyvals[230] > 1:
                if qtyvals[229] > 1:
                    temp=0
                qtyvals[338] = temp
                # 230 skipped

            elif cid == 341:
                if my_verbose>0: print("caulk at tub/shower base")
                temp=0
                if qtyvals[339] > 0:
                    temp = 1
                qtyvals[241] = temp

            elif cid == 354:
                if my_verbose>0: print("install under cab light fixtures")
                qtyvals[354] = qtyvals[192]

            elif cid == 286:
                if my_verbose>0: print("sink,faucet,dishwasher,disposal")
                qtyvals[286] = qtyvals[3]
            
            elif cid == 293:
                if my_verbose>0: print("reinstall existing base trim")
                qtyvals[293] = qtyvals[463]
            
            elif cid == 146:
                if my_verbose>0: print("stain and varnish new trim")
                temp = 0
                temp = qtyvals[293]+qtyvals[295]+qtyvals[296]+qtyvals[302]+qtyvals[303]+qtyvals[297]+qtyvals[298]
                qtyvals[146]=temp
                #skipped 294

            elif cid == 313:
                if my_verbose>0: print("stain and varnish new door/jam")
                if (qtyvals[299]+qtyvals[300]) > 0:
                    qtyvals[313]=1


        # 4. update the database with the new items.
        # IS THIS A GOOD IDEA?? CONFUZZLED.
        # Added check for new values set to 0, don't save it then.
        for item in SiteworkQuoteLine.objects.filter(quote=quoteid):
            if my_verbose>0: print("item id ",item.id,"item.quantity=",item.quantity,"qtyitem.calckey",qtyvals[item.calckey])
            
            if item.quantity != qtyvals[item.calckey] and qtyvals[item.calckey] > 0:
                if my_verbose>0: print("item id ",item.id)
                tempval = 0
                tempval = qtyvals[item.calckey]
                defaults={"quantity": tempval, "id":item.id}
                if my_verbose>0: print("item qty changed",item.calckey,"old=",item.quantity, "new ",tempval)

                # now change the db BOOM!!!!
                ####item.quantity = tempval
                ####item.save()
                #SiteworkQuoteLine.objects.filter(quote=quoteid,calckey=item.calckey).update(quantity=tempval)

        # for all sitework items in this quote where quantity > 0
        drywall = {item.drywall for item in SiteworkQuoteLine.objects.filter(quote=quoteid,quantity__gt=0) }
        if my_verbose>0: print (drywall)
        # 352 is drywall repair.  558 is drywall setup
        drywall_sum = sum(drywall)
        if my_verbose>0: print("drywall sum=",drywall_sum)
        dws = 1 if drywall_sum > 0 else 0
        rows=SiteworkQuoteLine.objects.filter(quote=quoteid,calckey=352).update(quantity=drywall_sum)
        if my_verbose>0: print("352 update=",rows, " value=",drywall_sum)
        rows=SiteworkQuoteLine.objects.filter(quote=quoteid,calckey=558).update(quantity=dws)
        if my_verbose>0: print("558 update=",rows," value=", dws)

                
        # Once the qty's are calculated then another pass thru to calc the prices of everything.
        # initial labor calcs will use the global labor rates, but eventually we will use 
        # new minute-based calcs instead of dollar-based. Resuts are still in dollars.
        if my_verbose>0: print("END calcprice-----------------------")

        pass
    
        

class SiteworkQuoteLine(models.Model):
    # id
    # parent quote
    quote = models.ForeignKey(SiteworkQuote,on_delete=models.CASCADE,null=True,related_name='sql_quotes')
    # which category item do we describe
    cat = models.ForeignKey(SiteworkCat,on_delete=models.CASCADE,null=True,related_name='sql_cats')
    # SiteworkSubCat used to create this line. Not the same as our ID now in this quote.
    #subcat = models.ForeignKey(SiteworkSubCat,on_delete=models.CASCADE,null=True,related_name='sql_subcats')
    
    # This is the key to the SiteworkSubCat table, using the calckey field
    subcatkey = models.IntegerField(blank=False,default=0)

    # comment
    itemcomment = models.CharField(max_length=250,blank=False,default="")
    # quantity used
    quantity = models.IntegerField(blank=False,default=0)

    # these are all copied from subcat
    workdesc = models.CharField(max_length=250,blank=False,default="")
    quantitydesc = models.CharField(max_length=10,blank=False,default="")
    basecost = models.FloatField(blank=False,default=0)
    unitamount = models.FloatField(blank=False,default=0)
    orderby = models.IntegerField(blank=False,default=0)
    drywall = models.IntegerField(blank=False,default=0)
    allowance = models.FloatField(blank=False,default=0)
    material = models.FloatField(blank=False,default=0)
    labor = models.FloatField(blank=False,default=0)
    profit = models.FloatField(blank=False,default=0)
    subfee = models.FloatField(blank=False,default=0)
    status = models.CharField(max_length=1,blank=True)
    kbflag = models.CharField(max_length=1,blank=True)
    group = models.IntegerField(blank=False,default=0)
    editallowance = models.CharField(max_length=1,blank=True)
    #
    calckey = models.IntegerField(blank=False,default=0)

    # calculated price
    price = models.FloatField(blank=False,default=0) 
   

    def __str__(self):
        return f"{self.workdesc}"    

    objects = QuoteLineManager()
