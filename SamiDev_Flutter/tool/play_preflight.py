"""Fail closed on missing Play submission facts; optionally inspect AAB native ELF.

This checks recorded evidence and technical inputs, not Google's acceptance.
It never reads signing passwords, uploads artifacts, or changes audience settings.
"""
import argparse,datetime,json,re,struct,sys,zipfile
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]

def https_origin(value):
    try:
        url=urlsplit(value or '')
        return url.scheme=='https' and bool(url.hostname) and not(url.username or url.password or url.query or url.fragment) and url.path in ('','/') and url.hostname not in ('localhost','127.0.0.1','10.0.2.2') and not url.hostname.endswith(('.trycloudflare.com','.example','.test'))
    except ValueError:return False

def elf_page_errors(data,name):
    # Play's 16 KB native requirement concerns 64-bit libraries.
    if len(data)<16 or data[:4]!=b'\x7fELF':return [name+': not an ELF library']
    if data[4]!=2:return []
    if data[5]!=1:return [name+': unsupported ELF byte order']
    try:
        offset=struct.unpack_from('<Q',data,32)[0]
        size,count=struct.unpack_from('<HH',data,54)
        if size<56 or count==0 or offset+size*count>len(data):return [name+': malformed ELF headers']
        for index in range(count):
            ptype,flags,file_offset,vaddr,paddr,filesz,memsz,align=struct.unpack_from('<IIQQQQQQ',data,offset+index*size)
            if ptype==1 and (align<16384 or file_offset%16384!=vaddr%16384):return [name+': PT_LOAD is not 16 KB compatible']
    except (struct.error,IndexError):return [name+': truncated ELF headers']
    return []

def artifact_errors(path):
    errors=[]
    try:
        with zipfile.ZipFile(path) as bundle:
            names=bundle.namelist()
            if 'BundleConfig.pb' not in names or 'base/manifest/AndroidManifest.xml' not in names:errors.append('Artifact is not an Android App Bundle')
            if not any(n.startswith('base/lib/arm64-v8a/') and n.endswith('.so') for n in names):errors.append('Missing arm64-v8a native libraries')
            if not any(n.upper().startswith('META-INF/') and n.upper().endswith(('.RSA','.EC','.DSA')) for n in names):errors.append('Missing AAB signing certificate; use your upload key')
            for name in names:
                if name.endswith('.so'):errors.extend(elf_page_errors(bundle.read(name),name))
    except (OSError,zipfile.BadZipFile) as error:errors.append('Cannot read artifact: '+type(error).__name__)
    return errors

def readiness(root=ROOT,stage="submission"):
    operator=json.loads((root.parent/'SamiDev_Platform/legal/operator.json').read_text())
    release=json.loads((root/'play/release.json').read_text())
    errors=[]
    for field in ('operatorLegalName','operatingCountry'):
        if not operator.get(field):errors.append('Missing operator fact: '+field)
    for field in ('supportMailboxVerified','infrastructureRetentionReviewed'):
        if operator.get(field) is not True:errors.append('Unverified operator evidence: '+field)
    if operator.get('publicationStatus')!='published':errors.append('Public privacy/terms are still drafts')
    if not https_origin(release.get('apiOrigin')):errors.append('A stable HTTPS production apiOrigin is required (temporary tunnels are not accepted by this check)')
    for field in ('privacyUrl','deletionUrl'):
        try:
            url=urlsplit(release.get(field) or '')
            if url.scheme!='https' or not url.hostname or url.username or url.password or url.fragment:raise ValueError()
        except ValueError:errors.append('Invalid public '+field)
    if release.get('audienceMode') not in ('mixed-with-children','13-plus','18-plus'):errors.append('Target audience decision and implementation are pending')
    if release.get('audienceMode') == '18-plus':
        if release.get('minimumAge') != 18 or operator.get('androidMinimumAge') != 18:
            errors.append('Android 18-plus audience requires matching minimumAge=18')
        if release.get('childrenExperience') != 'not-offered-android' or operator.get('androidChildrenExperience') != 'not-offered':
            errors.append('Android 18-plus must not offer a children experience')
    elif operator.get('audienceIncludesUnder13'):
        if release.get('audienceMode')!='mixed-with-children' or release.get('childrenExperience')!='offline-local-v1':errors.append('Under-13 audience requires the implemented isolated local-only mobile experience')
        if operator.get('childrenSafeguardsReviewed') is not True:errors.append('Under-13 local-only experience is implemented but documented Families/market compliance review remains unverified; no online parental-consent flow is enabled')
    elif release.get('audienceMode')!='13-plus':errors.append('Target audience disagrees with operator.json')
    fields=['reviewerAccessVerified','dataSafetyReviewed','contentRatingCompleted','contentRightsEvidenceReviewed']
    if stage=='submission':fields+=['realDeviceTestsPassed','preLaunchReportReviewed']
    for field in fields:
        if release.get(field) is not True:errors.append('Missing submission evidence: '+field)
    if type(release.get('chatAiEnabled')) is not bool:errors.append('Declare whether external AI chat is enabled in production')
    elif release['chatAiEnabled']:errors.append('External AI chat uses isolated memory without an account-deletion bridge; implement its data lifecycle before enabling it in a Play launch')
    try:
        reviewed=datetime.date.fromisoformat(release.get('policyReviewDate') or '')
        if not 0<=(datetime.date.today()-reviewed).days<=30:raise ValueError()
    except ValueError:errors.append('Review current official Play requirements and record policyReviewDate (within 30 days)')
    gradle=(root/'android/app/build.gradle.kts').read_text()
    package=re.search(r'applicationId\s*=\s*"([^"]+)"',gradle)
    if not package or package.group(1)!=release.get('applicationId'):errors.append('Application ID differs from Play release inputs')
    if 'isDebuggable = false' not in gradle:errors.append('Release debuggable must be explicitly false')
    return errors

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--artifact',type=Path);parser.add_argument('--artifact-only',action='store_true')
    parser.add_argument('--stage',choices=('build','submission'),default='submission')
    args=parser.parse_args()
    if args.artifact_only and not args.artifact:parser.error('--artifact-only requires --artifact')
    errors=[] if args.artifact_only else readiness(stage=args.stage)
    if args.artifact:errors+=artifact_errors(args.artifact)
    elif args.stage=='submission':errors.append('A signed AAB must be inspected with --artifact before claiming submission readiness')
    print(json.dumps({'ready':not errors,'scope':'artifact' if args.artifact_only else 'submission','artifactInspected':bool(args.artifact),'errors':errors,'note':'Not a Play approval. ELF checks do not verify generated APK ZIP alignment, signature authenticity, devices, policies or Play Console declarations.'},ensure_ascii=False,indent=2))
    return 1 if errors else 0
if __name__=='__main__':sys.exit(main())
