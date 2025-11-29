from django import forms
from admin_panel.models import *

# Product Form
class AdminLoginForm(forms.Form):
    name = forms.CharField(max_length=100)
    password = forms.CharField(widget=forms.PasswordInput)
    profile_picture = forms.ImageField(required=False)

class AdminPasswordChangeForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput)
    new_password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(ProductForm, self).__init__(*args, **kwargs)
        self.fields['category'].widget.attrs.update({'id': 'id_category'})
        


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        
        exclude=['discounted_price','offer_code','offer_start_time','offer_end_time']

class GiftSetForm(forms.ModelForm):
    class Meta:
        model = GiftSet
        
        exclude=['discounted_price','offer_code','offer_start_time','offer_end_time']


    def __init__(self, *args, **kwargs):
        super(GiftSetForm, self).__init__(*args, **kwargs)
        self.fields['flavours'].widget = forms.CheckboxSelectMultiple()
        self.fields['flavours'].queryset = self.fields['flavours'].queryset.distinct()


# Category Form
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = '__all__'
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter category name'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

# Subcategory Form
class SubCategoryForm(forms.ModelForm):
    class Meta:
        model = Subcategory
        fields = '__all__'
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter subcategory name'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'sub_image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'banner': forms.ClearableFileInput(attrs={'class': 'form-control'}),

        }

from .models import Banner

class BannerForm(forms.ModelForm):
    class Meta:
        model = Banner
        fields = '__all__'

class FlavourForm(forms.ModelForm):
    class Meta:
        model=Flavour
        fields='__all__'
        widgets={
            'name':forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter flavour name'}),
            'image':forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
        

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = '__all__'
        exclude = ['user', 'created_at']
        widgets = {
            'rating': forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            'review_text': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Write your review...'})
        }



class PremiumFestiveOfferForm(forms.ModelForm):
    class Meta:
        model = PremiumFestiveOffer
        fields = [
            'premium_festival',
            'offer_name',
            'category',
            'subcategory',
            'size',
            'code',
            'percentage',
            'start_date',
            'end_date',
            'is_active',
        ]
        widgets = {
            'premium_festival': forms.Select(attrs={'class': 'form-select'}),
            'offer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Offer name'}),
            'category': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'subcategory': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'size': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Size or All'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional code'}),
            'percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'e.g., 10'}),
            'start_date': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'}
            ),
            'end_date': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'}
            ),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_percentage(self):
        value = self.cleaned_data.get('percentage')
        if value is not None and (value < 0 or value > 100):
            raise forms.ValidationError("Percentage must be between 0 and 100.")
        return value

    def clean_start_date(self):
        premium_festival = self.cleaned_data.get("premium_festival") or ""
        print("DEBUG: clean_start_date premium_festival =", premium_festival)
        start_date = self.cleaned_data.get("start_date")
        if premium_festival in ("Welcome", "Premium"):
           return None
        return start_date

    def clean_end_date(self):
        premium_festival = self.cleaned_data.get("premium_festival") or ""
        print("DEBUG: clean_end_date premium_festival =", premium_festival)
        end_date = self.cleaned_data.get("end_date")
        if premium_festival in ("Welcome", "Premium"):
            return None
        return end_date


    def clean(self):
        cleaned_data = super().clean()
        premium_festival = cleaned_data.get("premium_festival")
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        # If it's not Welcome or Premium, validate dates are required
        if premium_festival not in ("Welcome", "Premium"):
            if not start_date:
                self.add_error("start_date", "Start date is required.")
            if not end_date:
                self.add_error("end_date", "End date is required.")
        return cleaned_data

class CouponForm(forms.ModelForm):
    class Meta:
        model=Coupon
        fields='__all__'
        exclude=['is_active']


class ProductVideoForm(forms.ModelForm):
    class Meta:
        model=ProductVideo
        fields='__all__'
        widgets = {
            'related_products': forms.SelectMultiple(attrs={'class': 'form-select'}),
        }

class SubscriptionForm(forms.ModelForm):
    class Meta:
        model=Subscription
        fields='__all__'
        

class ClientReviewForm(forms.ModelForm):
    class Meta:
        model = Client_review
        fields = ['client_name', 'review']
        widgets = {
            'client_name': forms.TextInput(attrs={'placeholder': 'Enter User Name', 'class': 'form-control'}),
            'review': forms.Textarea(attrs={'placeholder': 'Enter Review', 'class': 'form-control', 'rows': 4}),
        }