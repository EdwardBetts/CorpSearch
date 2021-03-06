# -*- coding: utf-8 -*-

from .models import Corporation, LegalFormLookup, Extract
from apps.person.models import Affiliation
from .forms import CorporationSearchForm
from apps.util.views import CsvResponseMixin

from django.db.models import Prefetch
from django.http import HttpResponsePermanentRedirect
from django.views.generic.list import ListView, BaseListView, MultipleObjectTemplateResponseMixin
from django.views.generic.detail import DetailView
from django.views.generic.base import TemplateView, RedirectView
from django.shortcuts import get_object_or_404
import json as simplejson

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

# Create your views here.

class CorporationListView(BaseListView):
    model = Corporation
    context_object_name = 'corporations'

    def get_queryset(self):
        qs = super(CorporationListView, self).get_queryset()

        # Prefetch related to save unnecessary queries. Sometimes, for some reason
        # extract date is not set, so the highest id should be the latest one.
        qs = qs.prefetch_related(Prefetch("extract_set", queryset=Extract.objects.order_by('-date', 'id'), to_attr='extracts'))
        return qs


class CorporationSearchView(CorporationListView):
    def get_queryset(self):
        qs = super(CorporationSearchView, self).get_queryset()

        form = CorporationSearchForm(self.request.GET)

        chosenIdCode = self.request.GET.get('id_code')
        if chosenIdCode:
            qs = qs.filter(id_code=chosenIdCode)

        chosenAddress = self.request.GET.get('address')
        if chosenAddress:
            qs = qs.filter(extract__address__icontains=chosenAddress).distinct()

        chosenEmail = self.request.GET.get('email')
        if chosenEmail:
            qs = qs.filter(extract__email__icontains=chosenEmail).distinct()

        chosenLegalFormId = self.request.GET.get('legal_form')
        if chosenLegalFormId and int(chosenLegalFormId) > 0:
            qs = qs.filter(extract__legalform__id=chosenLegalFormId)

        chosenName = self.request.GET.get('name')
        if chosenName:
            qs = qs.filter(name__icontains=chosenName)

        companiesRegisteredAfter = self.request.GET.get('companies_registered_after_0')
        if companiesRegisteredAfter:
            if len(companiesRegisteredAfter) == 4:
                companiesRegisteredAfter = companiesRegisteredAfter+"-01-01";

            if (len(companiesRegisteredAfter) == 10 or len(companiesRegisteredAfter) == 4):
                qs = qs.filter(registration_date__gte=companiesRegisteredAfter)

        companiesRegisteredBefore = self.request.GET.get('companies_registered_before_0')
        if companiesRegisteredBefore:
            if len(companiesRegisteredBefore) == 4:
                companiesRegisteredBefore = companiesRegisteredBefore+"-01-01";

            if (len(companiesRegisteredBefore) == 10 or len(companiesRegisteredBefore) == 4):
                qs = qs.filter(registration_date__lte=companiesRegisteredBefore)

        return qs.order_by('name')


class CorporationPagedTemplateSearchView(CorporationSearchView, MultipleObjectTemplateResponseMixin):
    paginate_by = 100


class CorporationCsvSearchView(CorporationSearchView, CsvResponseMixin):
    additional_fields = {'extracts': ('address',)}


class CorporationDetailView(DetailView):
    model = Corporation
    context_object_name = 'corporation'

    def get_object(self, queryset=None):
        #check if object is already cached
        if not getattr(self, 'object', None):
            #id_code of corporation seems to be 9 characters long, all other id's are pk
            if len(self.kwargs['id_code']) < 9:
                obj = get_object_or_404(Corporation, pk=self.kwargs['id_code'])
            else:
                obj = get_object_or_404(Corporation, id_code=self.kwargs['id_code'])
            return obj

    def get(self, request, *args, **kwargs):
        """
        Override main get method in order to preserve old url structure, where corporations were accessed by pk
        and not by id_code. This is needed until we import next batch of scraped data, pks will be replaced anyway.
        But by that time, Google will probably already detect 301 redirects.

        @todo: Remove this override when we run the next batch of import
        """
        self.object = self.get_object()
        obj_real_url = self.object.get_absolute_url()
        if self.request.path != obj_real_url:
            return HttpResponsePermanentRedirect(obj_real_url)
        else:
            context = self.get_context_data(object=self.object)
            return self.render_to_response(context)
    
    def get_context_data(self, **kwargs):
        context = super(CorporationDetailView, self).get_context_data(**kwargs)
        
        corpId = str(self.kwargs['id_code'])
        try:
            mostRecentDate = context['corporation'].affiliation_set.exclude(valid_date__isnull=True).latest().valid_date
        except Affiliation.DoesNotExist:
            mostRecentDate = None


        if mostRecentDate:
            affiliationForShares = context['corporation'].affiliation_set.filter(valid_date__exact=mostRecentDate)

            totalShare = 0.0
            for a in affiliationForShares:
                if a.share:
                    totalShare = totalShare + a.share

            shares = []
            if (totalShare == 1.0):
                shares.append(['Name','Shares'])
                for a in affiliationForShares:
                    if a.share:
                        thisShare = [a.person.name, a.share]
                        shares.append(thisShare)



                shares = simplejson.dumps(shares)
                context['shares'] = shares
        
               
        return context


