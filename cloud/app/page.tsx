import {requireChatGPTUser} from './chatgpt-auth';
import AcademyClient from './academy-client';
export const dynamic='force-dynamic';
export default async function Home(){await requireChatGPTUser('/');return <AcademyClient/>;}
